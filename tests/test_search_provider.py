"""`search/` paketinin (SearchProvider sözleşmesi + SearXNGProvider) testleri.

İş emri madde 18: bu testler GERÇEK ağa/SearXNG'ye hiç çıkmaz -- `SearXNGProvider`'a
sahte bir `opener` enjekte edilir (bkz. `_FakeResponse`/`_fake_opener_returning`), böylece
regression suite tamamen ağdan bağımsız ve deterministiktir. Gerçek SearXNG'ye karşı
çalışan canlı benchmark ayrı bir adımdır (bu iş emrinin B/C bölümleri) ve burada YOKTUR.
"""
import json
import socket
import urllib.error

from search.provider import SearchOptions, SearchOutcome, SearchProviderError, SearchResult
from search.searxng_provider import SearXNGProvider


class _FakeResponse:
    """`urllib.request.urlopen(...)` çağrısının `with ... as response:` bloğunu taklit eder."""

    def __init__(self, body_bytes):
        self._body = body_bytes

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _fake_opener_returning(payload_dict):
    body = json.dumps(payload_dict).encode("utf-8")

    def _opener(request, timeout=None):
        return _FakeResponse(body)

    return _opener


def _fake_opener_raising(exc):
    def _opener(request, timeout=None):
        raise exc

    return _opener


def _base_payload(results=None, unresponsive=None):
    return {
        "query": "test",
        "results": results if results is not None else [],
        "unresponsive_engines": unresponsive if unresponsive is not None else [],
    }


# --- 1. JSON parse (mutlu yol) ---------------------------------------------------------


def test_search_provider_parses_valid_json_response():
    payload = _base_payload(results=[
        {"title": "Örnek Başlık", "url": "https://example.com/a", "content": "içerik",
         "engine": "google cse", "engines": ["google cse", "brave"], "category": "general",
         "score": 3.5, "publishedDate": "2026-01-01T00:00:00"},
    ])
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("muhasebe")
    assert isinstance(outcome, SearchOutcome)
    assert len(outcome.results) == 1
    r = outcome.results[0]
    assert isinstance(r, SearchResult)
    assert r.title == "Örnek Başlık"
    assert r.url == "https://example.com/a"
    assert r.score == 3.5


# --- 2. Boş sonuç ------------------------------------------------------------------------


def test_search_provider_handles_empty_results_list():
    provider = SearXNGProvider(opener=_fake_opener_returning(_base_payload(results=[])))
    outcome = provider.search("hiçbir şey bulunamayacak sorgu")
    assert outcome.results == ()
    assert outcome.degraded is False


def test_search_provider_handles_empty_query_without_network_call():
    calls = []

    def _opener(request, timeout=None):
        calls.append(request)
        return _FakeResponse(json.dumps(_base_payload()).encode("utf-8"))

    provider = SearXNGProvider(opener=_opener)
    outcome = provider.search("   ")
    assert outcome.results == ()
    assert calls == []  # boş sorguda hiç ağ çağrısı yapılmamalı


# --- 3. Malformed result ------------------------------------------------------------------


def test_search_provider_skips_malformed_result_items_without_crashing():
    payload = _base_payload(results=[
        "bu bir dict değil",
        {"title": "Geçerli", "url": "https://example.com/valid", "content": "x", "engine": "brave"},
        {"title": "URL yok"},  # url alanı eksik -- atlanmalı
        None,
    ])
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("test")
    assert len(outcome.results) == 1
    assert outcome.results[0].url == "https://example.com/valid"


def test_search_provider_raises_typed_error_on_non_dict_top_level_payload():
    def _opener(request, timeout=None):
        return _FakeResponse(json.dumps([1, 2, 3]).encode("utf-8"))

    provider = SearXNGProvider(opener=_opener)
    try:
        provider.search("test")
        assert False, "SearchProviderError bekleniyordu"
    except SearchProviderError:
        pass


def test_search_provider_raises_typed_error_on_malformed_json_body():
    def _opener(request, timeout=None):
        return _FakeResponse(b"{ bozuk json ]")

    provider = SearXNGProvider(opener=_opener)
    try:
        provider.search("test")
        assert False, "SearchProviderError bekleniyordu"
    except SearchProviderError:
        pass


# --- 4. Timeout ----------------------------------------------------------------------------


def test_search_provider_raises_typed_error_on_timeout():
    provider = SearXNGProvider(opener=_fake_opener_raising(TimeoutError("zaman asimi")))
    try:
        provider.search("test")
        assert False, "SearchProviderError bekleniyordu"
    except SearchProviderError as exc:
        assert "erisilemedi" in str(exc) or "zaman" in str(exc).lower()


def test_search_provider_raises_typed_error_on_connection_refused():
    provider = SearXNGProvider(opener=_fake_opener_raising(
        urllib.error.URLError(ConnectionRefusedError("baglanti reddedildi"))
    ))
    try:
        provider.search("test")
        assert False, "SearchProviderError bekleniyordu"
    except SearchProviderError:
        pass


def test_search_provider_raises_typed_error_on_socket_timeout_os_error():
    provider = SearXNGProvider(opener=_fake_opener_raising(socket.timeout("zaman asimi")))
    try:
        provider.search("test")
        assert False, "SearchProviderError bekleniyordu"
    except SearchProviderError:
        pass


# --- 5. HTTP hatası --------------------------------------------------------------------------


def test_search_provider_raises_typed_error_on_http_error():
    exc = urllib.error.HTTPError(url="http://127.0.0.1:8890/search", code=500, msg="Internal Error",
                                  hdrs=None, fp=None)
    provider = SearXNGProvider(opener=_fake_opener_raising(exc))
    try:
        provider.search("test")
        assert False, "SearchProviderError bekleniyordu"
    except SearchProviderError as inner:
        assert "500" in str(inner)


# --- 6. Motor hatası (engine failure) / degraded gözlemlenebilirliği -------------------------


def test_search_provider_reports_unresponsive_engines_without_failing_the_call():
    payload = _base_payload(
        results=[{"title": "T", "url": "https://example.com/x", "content": "c", "engine": "google cse"}],
        unresponsive=[["duckduckgo", "CAPTCHA"], ["brave", "Askıya alındı: çok fazla istek"]],
    )
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("test")
    assert len(outcome.results) == 1  # bir motor düşse de elde olan sonuç kaybolmaz
    assert outcome.degraded is True
    assert ("duckduckgo", "CAPTCHA") in outcome.engines_failed
    assert ("brave", "Askıya alındı: çok fazla istek") in outcome.engines_failed


def test_search_provider_total_engine_outage_returns_empty_results_and_degraded_true():
    payload = _base_payload(
        results=[],
        unresponsive=[["google cse", "Askıya alındı: çok fazla istek"], ["duckduckgo", "CAPTCHA"],
                      ["brave", "Askıya alındı: çok fazla istek"]],
    )
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("test")
    # Bu, 2026-09-23 benchmarkında gerçekten gözlemlenen durumu birebir modelliyor:
    # tüm genel motorlar askıya alınınca sonuç 0/0 oluyor -- çağıran kod bunu ayırt
    # edebilmeli (degraded=True + results=()), "sonuç yok" ile "sistem düştü"yü karıştırmamalı.
    assert outcome.results == ()
    assert outcome.degraded is True
    assert len(outcome.engines_failed) == 3


# --- 7. Domain filtreleme (site: enjeksiyonu) -------------------------------------------------


def test_search_provider_injects_site_operator_for_each_requested_domain():
    captured = {}

    def _opener(request, timeout=None):
        captured["url"] = request.full_url
        return _FakeResponse(json.dumps(_base_payload()).encode("utf-8"))

    provider = SearXNGProvider(opener=_opener)
    provider.search("gelir vergisi tarifesi", SearchOptions(domains=("gib.gov.tr",)))
    assert "site%3Agib.gov.tr" in captured["url"] or "site:gib.gov.tr" in captured["url"]


def test_search_provider_injects_multiple_site_operators_for_multiple_domains():
    captured = {}

    def _opener(request, timeout=None):
        captured["url"] = request.full_url
        return _FakeResponse(json.dumps(_base_payload()).encode("utf-8"))

    provider = SearXNGProvider(opener=_opener)
    provider.search("staj", SearchOptions(domains=("turmob.org.tr", "gib.gov.tr")))
    decoded = urllib_unquote(captured["url"])
    assert "site:turmob.org.tr" in decoded
    assert "site:gib.gov.tr" in decoded


def urllib_unquote(url):
    import urllib.parse
    return urllib.parse.unquote(url)


# --- 8. Yinelenen URL (duplicate URL) ----------------------------------------------------------


def test_search_provider_deduplicates_results_sharing_the_same_url():
    payload = _base_payload(results=[
        {"title": "A (google cse)", "url": "https://gib.gov.tr/x", "content": "c1", "engine": "google cse"},
        {"title": "A (brave)", "url": "https://gib.gov.tr/x", "content": "c2", "engine": "brave"},
        {"title": "B", "url": "https://gib.gov.tr/y", "content": "c3", "engine": "google cse"},
    ])
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("test")
    urls = [r.url for r in outcome.results]
    assert urls == ["https://gib.gov.tr/x", "https://gib.gov.tr/y"]
    assert len(urls) == len(set(urls))


# --- 9. PDF tespiti ------------------------------------------------------------------------------


def test_search_provider_detects_pdf_results_by_url_extension():
    payload = _base_payload(results=[
        {"title": "Tarife PDF", "url": "https://cdn.gib.gov.tr/dosya/tarife.pdf?objectKey=x",
         "content": "c", "engine": "google cse"},
        {"title": "Normal sayfa", "url": "https://gib.gov.tr/vergi-konulari", "content": "c",
         "engine": "google cse"},
    ])
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("test")
    by_url = {r.url: r for r in outcome.results}
    assert by_url["https://cdn.gib.gov.tr/dosya/tarife.pdf?objectKey=x"].is_pdf is True
    assert by_url["https://gib.gov.tr/vergi-konulari"].is_pdf is False


# --- 10. Türkçe Unicode --------------------------------------------------------------------------


def test_search_provider_round_trips_turkish_unicode_in_query_and_results():
    turkish_title = "Gelir Vergisi Tarifesi 2026 — Şüpheli Alacaklar, Öğrenim Gideri"
    payload = _base_payload(results=[
        {"title": turkish_title, "url": "https://example.com/tr", "content": "İçerik: özel karakterler çöğüşıİĞÜŞÖÇ",
         "engine": "google cse"},
    ])
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("4/a 4/b 4/c sigortalılık farkı — Bağ-Kur")
    assert outcome.results[0].title == turkish_title
    assert "çöğüşıİĞÜŞÖÇ" in outcome.results[0].snippet
    assert outcome.query == "4/a 4/b 4/c sigortalılık farkı — Bağ-Kur"


# --- 11. Sonuç normalizasyonu (tüm SearchResult alanları) ------------------------------------------


def test_search_provider_normalizes_all_search_result_fields():
    payload = _base_payload(results=[
        {"title": "Başlık", "url": "https://www.sgk.gov.tr/duyuru/x", "content": "özet metni",
         "engine": "duckduckgo", "engines": ["duckduckgo", "brave"], "category": "general",
         "score": 7.25, "publishedDate": "2026-04-09T00:00:00"},
    ])
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("SGK duyuru")
    r = outcome.results[0]
    assert r.title == "Başlık"
    assert r.url == "https://www.sgk.gov.tr/duyuru/x"
    assert r.snippet == "özet metni"
    assert r.engine == "duckduckgo"
    assert r.engines == ("duckduckgo", "brave")
    assert r.category == "general"
    assert r.score == 7.25
    assert r.published_date == "2026-04-09T00:00:00"
    assert r.domain == "www.sgk.gov.tr"
    assert r.is_pdf is False
    assert r.query == "SGK duyuru"


def test_search_provider_normalizes_missing_optional_fields_to_safe_defaults():
    payload = _base_payload(results=[{"url": "https://example.com/bare"}])
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("test")
    r = outcome.results[0]
    assert r.title == ""
    assert r.snippet == ""
    assert r.engine == ""
    assert r.engines == ()
    assert r.score is None
    assert r.published_date is None


def test_search_provider_respects_limit_option():
    payload = _base_payload(results=[
        {"title": f"Sonuç {i}", "url": f"https://example.com/{i}", "content": "c", "engine": "google cse"}
        for i in range(10)
    ])
    provider = SearXNGProvider(opener=_fake_opener_returning(payload))
    outcome = provider.search("test", SearchOptions(limit=3))
    assert len(outcome.results) == 3


def run_all():
    test_search_provider_parses_valid_json_response()
    test_search_provider_handles_empty_results_list()
    test_search_provider_handles_empty_query_without_network_call()
    test_search_provider_skips_malformed_result_items_without_crashing()
    test_search_provider_raises_typed_error_on_non_dict_top_level_payload()
    test_search_provider_raises_typed_error_on_malformed_json_body()
    test_search_provider_raises_typed_error_on_timeout()
    test_search_provider_raises_typed_error_on_connection_refused()
    test_search_provider_raises_typed_error_on_socket_timeout_os_error()
    test_search_provider_raises_typed_error_on_http_error()
    test_search_provider_reports_unresponsive_engines_without_failing_the_call()
    test_search_provider_total_engine_outage_returns_empty_results_and_degraded_true()
    test_search_provider_injects_site_operator_for_each_requested_domain()
    test_search_provider_injects_multiple_site_operators_for_multiple_domains()
    test_search_provider_deduplicates_results_sharing_the_same_url()
    test_search_provider_detects_pdf_results_by_url_extension()
    test_search_provider_round_trips_turkish_unicode_in_query_and_results()
    test_search_provider_normalizes_all_search_result_fields()
    test_search_provider_normalizes_missing_optional_fields_to_safe_defaults()
    test_search_provider_respects_limit_option()
    print("KAIZEN SEARCHPROVIDER TESTLERI: BASARILI (20 test)")


if __name__ == "__main__":
    run_all()
