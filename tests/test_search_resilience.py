"""`search/` paketinin dayanıklılık (resilience) testleri -- iş emri "Search Resilience v1".

Bu dosya `tests/test_search_provider.py`'yi (Faz A/B'nin 20 orijinal testi) BİLEREK
değiştirmez -- o dosyadaki hiçbir test satırı bu iş emrinde dokunulmadı (iş emri madde 1:
"Mevcut davranışı gereksiz yere yeniden yazma"). Bu dosya yalnızca YENİ eklenen retry/
backoff/burst-koruması/health/fallback/observability davranışlarını test eder.

Madde 18/12: hiçbir test GERÇEK ağa çıkmaz ve GERÇEK bekleme (time.sleep) kullanmaz --
`opener` (ağ) ve `sleep`/`clock` (zaman) sahte (fake) enjekte edilir, tıpkı
`test_search_provider.py`'deki `opener` deseninde olduğu gibi.
"""
import json
import urllib.error

from search.provider import (
    FALLBACK_REASON_DEGRADED_NO_RESULTS,
    FALLBACK_REASON_RATE_LIMITED,
    FALLBACK_REASON_TIMEOUT,
    FALLBACK_REASON_UNAVAILABLE,
    HEALTH_COOLDOWN,
    HEALTH_DEGRADED,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    STATUS_DEGRADED,
    STATUS_EMPTY,
    STATUS_OK,
    STATUS_RATE_LIMITED,
    STATUS_TIMEOUT,
    STATUS_UNAVAILABLE,
    SearchOptions,
    SearchProviderError,
    SearchRateLimitedError,
    SearchTimeoutError,
    SearchUnavailableError,
)
from search.searxng_provider import SearXNGProvider


# --- Test yardımcıları (fake opener/sleep/clock -- gerçek ağ/zaman KULLANILMAZ) -----------


class _FakeResponse:
    def __init__(self, body_bytes):
        self._body = body_bytes

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _payload(results=None, unresponsive=None):
    return {
        "query": "test",
        "results": results if results is not None else [],
        "unresponsive_engines": unresponsive if unresponsive is not None else [],
    }


class _FakeClock:
    """Enjekte edilebilir sahte saat -- gerçek zaman GEÇMEZ, yalnızca `advance()` ile
    kontrollü biçimde ilerletilir (backoff/cooldown/burst testlerinin deterministik ve
    anlık olmasını sağlar)."""

    def __init__(self, start=1000.0):
        self._now = start

    def advance(self, seconds):
        self._now += seconds

    def __call__(self):
        return self._now


class _SleepRecorder:
    """Enjekte edilebilir sahte `sleep` -- GERÇEKTEN beklemez, yalnızca çağrıları kaydeder.
    Bir `_FakeClock`'a bağlıysa, kaydın yanı sıra saati de o kadar ileri alır (böylece
    cooldown/min-interval hesapları da testte doğru ilerler)."""

    def __init__(self, clock: _FakeClock | None = None):
        self.calls = []
        self._clock = clock

    def __call__(self, seconds):
        self.calls.append(seconds)
        if self._clock is not None:
            self._clock.advance(seconds)


def _opener_sequence(*behaviors):
    """Her çağrıda `behaviors` listesindeki bir sonraki davranışı uygular. Davranış ya bir
    `Exception` örneğidir (fırlatılır) ya da bir `dict` payload'dır (başarılı yanıt olarak
    döner). Liste tükenirse son davranış tekrarlanır."""

    calls = []

    def _opener(request, timeout=None):
        calls.append(request)
        idx = min(len(calls) - 1, len(behaviors) - 1)
        behavior = behaviors[idx]
        if isinstance(behavior, BaseException):
            raise behavior
        return _FakeResponse(json.dumps(behavior).encode("utf-8"))

    _opener.calls = calls
    return _opener


def _http_error(code, headers=None):
    return urllib.error.HTTPError(
        url="http://127.0.0.1:8890/search", code=code, msg=f"HTTP {code}", hdrs=headers, fp=None
    )


# --- 1. Retry sonrası başarı (retry-then-success) -----------------------------------------


def test_search_resilience_retries_and_succeeds_after_transient_timeout():
    opener = _opener_sequence(TimeoutError("gecici zaman asimi"), _payload(results=[
        {"title": "T", "url": "https://example.com/a", "content": "c", "engine": "google cse"},
        {"title": "T2", "url": "https://example.com/b", "content": "c", "engine": "brave"},
    ]))
    sleeper = _SleepRecorder()
    provider = SearXNGProvider(opener=opener, max_attempts=3, sleep=sleeper, min_request_interval=0)
    outcome = provider.search("test")
    assert len(outcome.results) == 2
    assert len(opener.calls) == 2  # ilk deneme basarisiz, ikinci basarili
    assert len(sleeper.calls) == 1  # tam olarak bir kez backoff beklendi
    assert provider.health.state == HEALTH_HEALTHY  # basarili sonucla saglik toparlandi


# --- 2. Retry limiti tukendiginde tipli hata firlatilir ------------------------------------


def test_search_resilience_raises_after_retries_exhausted_on_persistent_timeout():
    opener = _opener_sequence(TimeoutError("surekli zaman asimi"))
    sleeper = _SleepRecorder()
    provider = SearXNGProvider(opener=opener, max_attempts=3, sleep=sleeper, min_request_interval=0)
    try:
        provider.search("test")
        assert False, "SearchTimeoutError bekleniyordu"
    except SearchTimeoutError as exc:
        assert exc.status == STATUS_TIMEOUT
        assert exc.fallback_reason == FALLBACK_REASON_TIMEOUT
    assert len(opener.calls) == 3  # max_attempts kadar denendi, sonsuz DEGIL
    assert len(sleeper.calls) == 2  # denemeler arasinda (3-1) kez backoff


# --- 3. Backoff enjekte edilebilir sleep kullanir, gercek bekleme YOK -----------------------


def test_search_resilience_backoff_uses_injectable_sleep_with_bounded_exponential_delay():
    opener = _opener_sequence(TimeoutError("t1"), TimeoutError("t2"), TimeoutError("t3"))
    sleeper = _SleepRecorder()
    provider = SearXNGProvider(
        opener=opener, max_attempts=4, sleep=sleeper, min_request_interval=0,
        backoff_base=0.2, backoff_max=1.0,
    )
    try:
        provider.search("test")
    except SearchTimeoutError:
        pass
    # Sinirli/artan (bounded exponential) gecikmeler: 0.2, 0.4, 0.8 -- gercek zaman GECMEZ.
    assert sleeper.calls == [0.2, 0.4, 0.8]


# --- 4. HTTP 429 -> RATE_LIMITED, retry_after header'dan okunur -----------------------------


def test_search_resilience_http_429_raises_rate_limited_error_with_retry_after():
    opener = _opener_sequence(_http_error(429, headers={"Retry-After": "12"}))
    sleeper = _SleepRecorder()
    provider = SearXNGProvider(opener=opener, max_attempts=1, sleep=sleeper, min_request_interval=0)
    try:
        provider.search("test")
        assert False, "SearchRateLimitedError bekleniyordu"
    except SearchRateLimitedError as exc:
        assert exc.status == STATUS_RATE_LIMITED
        assert exc.fallback_reason == FALLBACK_REASON_RATE_LIMITED
        assert exc.retry_after == 12.0
    assert provider.health.state == HEALTH_COOLDOWN
    assert provider.health.cooldown_until is not None


# --- 5. HTTP 500/502/503 -> retryable, sonunda UNAVAILABLE ----------------------------------


def test_search_resilience_http_500_502_503_are_retryable_and_map_to_unavailable():
    for code in (500, 502, 503):
        opener = _opener_sequence(_http_error(code))
        provider = SearXNGProvider(
            opener=opener, max_attempts=2, sleep=_SleepRecorder(), min_request_interval=0
        )
        try:
            provider.search("test")
            assert False, f"SearchUnavailableError bekleniyordu (HTTP {code})"
        except SearchUnavailableError as exc:
            assert exc.status == STATUS_UNAVAILABLE
            assert str(code) in str(exc)
        assert len(opener.calls) == 2  # retry uygulandi (max_attempts kadar)


# --- 6. Retryable OLMAYAN durumlar -- gereksiz deneme YOK ------------------------------------


def test_search_resilience_http_404_is_not_retried():
    opener = _opener_sequence(_http_error(404))
    sleeper = _SleepRecorder()
    provider = SearXNGProvider(opener=opener, max_attempts=5, sleep=sleeper, min_request_interval=0)
    try:
        provider.search("test")
        assert False, "SearchProviderError bekleniyordu"
    except SearchProviderError as exc:
        assert not isinstance(exc, (SearchTimeoutError, SearchRateLimitedError, SearchUnavailableError))
    assert len(opener.calls) == 1  # 404 kalici bir hata -- yeniden denenmedi
    assert sleeper.calls == []


def test_search_resilience_malformed_json_is_not_retried():
    calls = []

    def _opener(request, timeout=None):
        calls.append(request)
        return _FakeResponse(b"{ bozuk json ]")

    sleeper = _SleepRecorder()
    provider = SearXNGProvider(opener=_opener, max_attempts=5, sleep=sleeper, min_request_interval=0)
    try:
        provider.search("test")
        assert False, "SearchProviderError bekleniyordu"
    except SearchProviderError:
        pass
    assert len(calls) == 1  # bozuk gövdeyi tekrar istemek sonucu degistirmez
    assert sleeper.calls == []


def test_search_resilience_connection_refused_is_retryable_and_maps_to_unavailable():
    opener = _opener_sequence(urllib.error.URLError(ConnectionRefusedError("red")))
    provider = SearXNGProvider(
        opener=opener, max_attempts=2, sleep=_SleepRecorder(), min_request_interval=0
    )
    try:
        provider.search("test")
        assert False, "SearchUnavailableError bekleniyordu"
    except SearchUnavailableError as exc:
        assert exc.status == STATUS_UNAVAILABLE
    assert len(opener.calls) == 2


# --- 7. Search Status Contract: basarili / bos / motor hatasi ayirt edilir ------------------


def test_search_resilience_successful_search_status_is_ok():
    opener = _opener_sequence(_payload(results=[
        {"title": "T", "url": "https://example.com/a", "content": "c", "engine": "google cse"},
        {"title": "T2", "url": "https://example.com/b", "content": "c", "engine": "brave"},
    ]))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("test")
    assert outcome.status == STATUS_OK
    assert outcome.fallback_recommended is False


def test_search_resilience_empty_results_status_is_empty_not_error():
    opener = _opener_sequence(_payload(results=[]))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("hicbir sonuc bulunamayacak sorgu")
    # KRITIK: "sonuc yok" (EMPTY) ile bir hata/DEGRADED durumu KARISTIRILMAMALI.
    assert outcome.status == STATUS_EMPTY
    assert outcome.fallback_recommended is False
    assert outcome.fallback_reason is None


# --- 8. Tek motora bagimlilik (single-engine dependency) sinyali ----------------------------


def test_search_resilience_single_engine_dependency_flagged_when_only_one_engine_contributes():
    opener = _opener_sequence(_payload(results=[
        {"title": "A", "url": "https://example.com/a", "content": "c", "engine": "google cse"},
        {"title": "B", "url": "https://example.com/b", "content": "c", "engine": "google cse"},
    ]))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("test")
    assert outcome.single_engine_dependency is True
    assert outcome.status == STATUS_DEGRADED


def test_search_resilience_multi_engine_results_not_flagged_as_single_engine_dependency():
    opener = _opener_sequence(_payload(results=[
        {"title": "A", "url": "https://example.com/a", "content": "c", "engine": "google cse"},
        {"title": "B", "url": "https://example.com/b", "content": "c", "engine": "brave"},
    ]))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("test")
    assert outcome.single_engine_dependency is False
    assert outcome.status == STATUS_OK


# --- 9. Bir motor duserken digeri basarili olursa sonuc yine de kullanilabilir --------------


def test_search_resilience_one_engine_broken_other_succeeds_still_returns_usable_results():
    opener = _opener_sequence(_payload(
        results=[{"title": "A", "url": "https://example.com/a", "content": "c", "engine": "brave"}],
        unresponsive=[["duckduckgo", "CAPTCHA"]],
    ))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("test")
    assert len(outcome.results) == 1
    assert outcome.degraded is True
    assert outcome.status == STATUS_DEGRADED
    # Kullanilabilir sonuc VAR -- zorunlu fallback onerilmez, ama degraded gorunur durumda.
    assert outcome.fallback_recommended is False


# --- 10. Tum motorlar duserse fallback ACIKCA onerilir, sebebi kaybolmaz --------------------


def test_search_resilience_total_engine_outage_recommends_fallback_with_reason():
    opener = _opener_sequence(_payload(
        results=[],
        unresponsive=[["google cse", "Askiya alindi"], ["duckduckgo", "CAPTCHA"], ["brave", "Askiya alindi"]],
    ))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("test")
    assert outcome.results == ()
    assert outcome.status == STATUS_DEGRADED
    assert outcome.fallback_recommended is True
    assert outcome.fallback_reason == FALLBACK_REASON_DEGRADED_NO_RESULTS


def test_search_resilience_fallback_not_needed_for_normal_result_case():
    opener = _opener_sequence(_payload(results=[
        {"title": "A", "url": "https://example.com/a", "content": "c", "engine": "google cse"},
        {"title": "B", "url": "https://example.com/b", "content": "c", "engine": "brave"},
    ]))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("test")
    assert outcome.fallback_recommended is False
    assert outcome.fallback_reason is None


# --- 11. Exception'lar ASLA sessizce bos SearchOutcome'a donusmez ---------------------------


def test_search_resilience_exceptions_are_never_silently_converted_to_empty_outcome():
    opener = _opener_sequence(urllib.error.URLError(OSError("kalici baglanti hatasi")))
    provider = SearXNGProvider(
        opener=opener, max_attempts=2, sleep=_SleepRecorder(), min_request_interval=0
    )
    raised = False
    try:
        outcome = provider.search("test")
        # Buraya asla ulasilmamali -- ulasilirsa kritik kural ihlal edilmis demektir.
        assert False, f"Hata sessizce SearchOutcome'a donustu: {outcome!r}"
    except SearchProviderError:
        raised = True
    assert raised is True


# --- 12. Provider Health: HEALTHY -> DEGRADED -> UNAVAILABLE -> HEALTHY gecisleri -----------


def test_search_resilience_provider_health_starts_healthy():
    provider = SearXNGProvider(opener=_opener_sequence(_payload()), min_request_interval=0)
    assert provider.health.state == HEALTH_HEALTHY
    assert provider.health.consecutive_failures == 0


def test_search_resilience_provider_health_becomes_unavailable_after_consecutive_failures():
    opener = _opener_sequence(urllib.error.URLError(OSError("hata")))
    provider = SearXNGProvider(
        opener=opener, max_attempts=1, sleep=_SleepRecorder(), min_request_interval=0,
        unavailable_after=2,
    )
    for _ in range(2):
        try:
            provider.search("test")
        except SearchProviderError:
            pass
    assert provider.health.state == HEALTH_UNAVAILABLE
    assert provider.health.consecutive_failures == 2


def test_search_resilience_provider_health_recovers_to_healthy_after_success_following_failures():
    opener = _opener_sequence(
        urllib.error.URLError(OSError("hata1")),
        urllib.error.URLError(OSError("hata2")),
        _payload(results=[
            {"title": "A", "url": "https://example.com/a", "content": "c", "engine": "brave"},
            {"title": "B", "url": "https://example.com/b", "content": "c", "engine": "google cse"},
        ]),
    )
    provider = SearXNGProvider(
        opener=opener, max_attempts=1, sleep=_SleepRecorder(), min_request_interval=0,
        unavailable_after=2,
    )
    for _ in range(2):
        try:
            provider.search("test")
        except SearchProviderError:
            pass
    assert provider.health.state == HEALTH_UNAVAILABLE
    outcome = provider.search("test")
    assert len(outcome.results) == 2
    assert provider.health.state == HEALTH_HEALTHY
    assert provider.health.consecutive_failures == 0


# --- 13. Rate limit -> cooldown -> sonraki cagri aga hic CIKMADAN hizli basarisiz olur ------


def test_search_resilience_rate_limit_triggers_cooldown_and_subsequent_call_fails_fast():
    clock = _FakeClock()
    opener = _opener_sequence(_http_error(429, headers={"Retry-After": "30"}))
    provider = SearXNGProvider(
        opener=opener, max_attempts=1, sleep=_SleepRecorder(clock), min_request_interval=0,
        clock=clock,
    )
    try:
        provider.search("ilk sorgu")
    except SearchRateLimitedError:
        pass
    assert len(opener.calls) == 1
    assert provider.health.state == HEALTH_COOLDOWN

    # Soguma suresi icinde (henuz ilerletilmedi) ikinci cagri: AGA HIC CIKMAMALI.
    try:
        provider.search("ikinci sorgu")
        assert False, "SearchRateLimitedError bekleniyordu (cooldown)"
    except SearchRateLimitedError as exc:
        assert exc.retry_after is not None and exc.retry_after > 0
    assert len(opener.calls) == 1  # ikinci cagri opener'i HIC cagirmadi


def test_search_resilience_cooldown_expires_and_next_call_reaches_network_again():
    clock = _FakeClock()
    opener = _opener_sequence(
        _http_error(429, headers={"Retry-After": "5"}),
        _payload(results=[{"title": "A", "url": "https://example.com/a", "content": "c", "engine": "brave"}]),
    )
    provider = SearXNGProvider(
        opener=opener, max_attempts=1, sleep=_SleepRecorder(clock), min_request_interval=0,
        clock=clock,
    )
    try:
        provider.search("ilk sorgu")
    except SearchRateLimitedError:
        pass
    clock.advance(10.0)  # soguma suresini (5s) asan bir ilerleme -- GERCEK bekleme YOK
    outcome = provider.search("ikinci sorgu")
    assert len(outcome.results) == 1
    assert len(opener.calls) == 2  # soguma bitince aga tekrar cikildi


# --- 14. Burst korumasi: minimum istek araligi enjekte edilebilir sleep ile saglanir --------


def test_search_resilience_burst_protection_enforces_minimum_interval_via_injectable_sleep():
    clock = _FakeClock()
    sleeper = _SleepRecorder(clock)
    opener = _opener_sequence(_payload(), _payload())
    provider = SearXNGProvider(
        opener=opener, sleep=sleeper, clock=clock, min_request_interval=2.0,
    )
    provider.search("birinci")
    provider.search("ikinci")  # saat hic ilerlemedi -- min araligi zorlamali
    assert any(delay >= 1.9 for delay in sleeper.calls)  # burst korumasi beklemesi kaydedildi


def test_search_resilience_burst_protection_does_not_delay_when_enough_time_has_passed():
    clock = _FakeClock()
    sleeper = _SleepRecorder(clock)
    opener = _opener_sequence(_payload(), _payload())
    provider = SearXNGProvider(
        opener=opener, sleep=sleeper, clock=clock, min_request_interval=2.0,
    )
    provider.search("birinci")
    clock.advance(5.0)  # asgari araligin cok uzerinde bir sure gecti
    calls_before = list(sleeper.calls)
    provider.search("ikinci")
    assert sleeper.calls == calls_before  # ek bir burst-korumasi beklemesi EKLENMEDI


# --- 15. Mevcut davranis (dedup / Turkce / PDF / domain filtre) resilience sarmalayicisiyla da bozulmadi --


def test_search_resilience_duplicate_url_dedup_still_works():
    opener = _opener_sequence(_payload(results=[
        {"title": "A1", "url": "https://gib.gov.tr/x", "content": "c1", "engine": "google cse"},
        {"title": "A2", "url": "https://gib.gov.tr/x", "content": "c2", "engine": "brave"},
        {"title": "B", "url": "https://gib.gov.tr/y", "content": "c3", "engine": "brave"},
    ]))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("test")
    # Yinelenen URL hâlâ atılıyor (ilk görülen tutulur) -- resilience sarmalayıcısı bu
    # davranışı DEĞİŞTİRMEDİ, iş emri madde 1'in "mevcut davranışı yeniden yazma" kuralı.
    assert len(outcome.results) == 2
    assert outcome.results[0].url == "https://gib.gov.tr/x"
    assert outcome.status in (STATUS_OK, STATUS_DEGRADED)


def test_search_resilience_turkish_unicode_preserved_with_new_status_fields():
    title = "Şüpheli Alacaklar — Öğrenim Gideri Çİğüşö"
    opener = _opener_sequence(_payload(results=[
        {"title": title, "url": "https://example.com/tr", "content": "içerik", "engine": "google cse"},
        {"title": "İkinci sonuç", "url": "https://example.com/tr2", "content": "başka içerik", "engine": "brave"},
    ]))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("Bağ-Kur 4/b sorgusu")
    assert outcome.results[0].title == title
    assert outcome.status == STATUS_OK


def test_search_resilience_pdf_detection_still_works():
    opener = _opener_sequence(_payload(results=[
        {"title": "Tarife", "url": "https://cdn.gib.gov.tr/x.pdf", "content": "c", "engine": "google cse"},
    ]))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    outcome = provider.search("test")
    assert outcome.results[0].is_pdf is True


def test_search_resilience_domain_filtering_still_applied_with_resilience_wrapper():
    captured = {}

    def _opener(request, timeout=None):
        captured["url"] = request.full_url
        return _FakeResponse(json.dumps(_payload()).encode("utf-8"))

    provider = SearXNGProvider(opener=_opener, min_request_interval=0)
    provider.search("gelir vergisi", SearchOptions(domains=("gib.gov.tr",)))
    assert "site%3Agib.gov.tr" in captured["url"] or "site:gib.gov.tr" in captured["url"]


# --- 16. Observability: minimal trace/debug metadata (madde 13) ----------------------------


def test_search_resilience_observability_debug_info_available_after_successful_call():
    opener = _opener_sequence(_payload(
        results=[{"title": "A", "url": "https://example.com/a", "content": "c", "engine": "brave"}],
        unresponsive=[["duckduckgo", "CAPTCHA"]],
    ))
    provider = SearXNGProvider(opener=opener, min_request_interval=0)
    assert provider.last_search_debug is None  # hic cagri yapilmadan once
    outcome = provider.search("test")
    debug = provider.last_search_debug
    assert debug is not None
    assert debug.provider == "searxng"
    assert debug.attempt_count == 1
    assert debug.elapsed >= 0.0
    assert debug.status == outcome.status
    assert debug.result_count == len(outcome.results)
    assert debug.active_engines == ("brave",)
    assert debug.unresponsive_engines == (("duckduckgo", "CAPTCHA"),)


def test_search_resilience_observability_debug_info_available_after_failed_call():
    opener = _opener_sequence(TimeoutError("t"))
    provider = SearXNGProvider(
        opener=opener, max_attempts=2, sleep=_SleepRecorder(), min_request_interval=0
    )
    try:
        provider.search("test")
    except SearchTimeoutError:
        pass
    debug = provider.last_search_debug
    assert debug is not None
    assert debug.attempt_count == 2
    assert debug.status == STATUS_TIMEOUT
    assert debug.fallback_recommended is True
    assert debug.fallback_reason == FALLBACK_REASON_TIMEOUT


def run_all():
    test_search_resilience_retries_and_succeeds_after_transient_timeout()
    test_search_resilience_raises_after_retries_exhausted_on_persistent_timeout()
    test_search_resilience_backoff_uses_injectable_sleep_with_bounded_exponential_delay()
    test_search_resilience_http_429_raises_rate_limited_error_with_retry_after()
    test_search_resilience_http_500_502_503_are_retryable_and_map_to_unavailable()
    test_search_resilience_http_404_is_not_retried()
    test_search_resilience_malformed_json_is_not_retried()
    test_search_resilience_connection_refused_is_retryable_and_maps_to_unavailable()
    test_search_resilience_successful_search_status_is_ok()
    test_search_resilience_empty_results_status_is_empty_not_error()
    test_search_resilience_single_engine_dependency_flagged_when_only_one_engine_contributes()
    test_search_resilience_multi_engine_results_not_flagged_as_single_engine_dependency()
    test_search_resilience_one_engine_broken_other_succeeds_still_returns_usable_results()
    test_search_resilience_total_engine_outage_recommends_fallback_with_reason()
    test_search_resilience_fallback_not_needed_for_normal_result_case()
    test_search_resilience_exceptions_are_never_silently_converted_to_empty_outcome()
    test_search_resilience_provider_health_starts_healthy()
    test_search_resilience_provider_health_becomes_unavailable_after_consecutive_failures()
    test_search_resilience_provider_health_recovers_to_healthy_after_success_following_failures()
    test_search_resilience_rate_limit_triggers_cooldown_and_subsequent_call_fails_fast()
    test_search_resilience_cooldown_expires_and_next_call_reaches_network_again()
    test_search_resilience_burst_protection_enforces_minimum_interval_via_injectable_sleep()
    test_search_resilience_burst_protection_does_not_delay_when_enough_time_has_passed()
    test_search_resilience_duplicate_url_dedup_still_works()
    test_search_resilience_turkish_unicode_preserved_with_new_status_fields()
    test_search_resilience_pdf_detection_still_works()
    test_search_resilience_domain_filtering_still_applied_with_resilience_wrapper()
    test_search_resilience_observability_debug_info_available_after_successful_call()
    test_search_resilience_observability_debug_info_available_after_failed_call()
    print("KAIZEN SEARCH RESILIENCE TESTLERI: BASARILI (29 test)")


if __name__ == "__main__":
    run_all()
