"""SearXNG için somut SearchProvider implementasyonu (iş emri Faz A/B + Search Resilience v1).

Bu sağlayıcı yalnızca Kaizen'in KENDİ bilgisayarındaki yerel SearXNG'ye (varsayılan
http://127.0.0.1:8890, bkz. `search/setup_searxng.ps1`) bağlanır. HENÜZ KaizenBrain'e
bağlı DEĞİLDİR (bkz. provider.py docstring'i ve iş emri madde 14) -- yalnızca bağımsız
olarak (bu dosyayı ve `tests/test_search_provider.py`'yi çağırarak) test edilmiştir.

Gerçekten desteklenen / desteklenmeyen seçenekler (2026-09-23 tarihli benchmarka göre,
bkz. KAIZEN_HEDEF_VE_YOL_HARITASI.md ilgili bölüm -- iş emrinin "gerçekten desteklemediği
özelliği varmış gibi gösterme" uyarısına uymak için burada açıkça yazılıdır):

- `categories`: SearXNG JSON API'sinin NATIVE, belgelenmiş parametresidir (`&categories=`).
- `language`: SearXNG JSON API'si `&language=` parametresini hatasız kabul ediyor, ANCAK bu
  oturumdaki benchmark'ta jenerik bir sorguyla test edildiği için gerçekten filtrelediği
  AYIRT EDİCİ biçimde kanıtlanamadı. Best-effort olarak gönderilir; sonraki fazda ayırt
  edici bir testle doğrulanmalı.
- `freshness`: SearXNG'nin `time_range` parametresine eşlenir; API hatasız kabul ediyor
  ama bu oturumda filtreleme etkisi (eski/yeni ayrımı) doğrulanamadı -- benchmark'ta
  `publishedDate` alanı neredeyse hep boş (None) döndü (google cse motoru tarih
  metadata'sı döndürmüyor), bu yüzden bu sağlayıcı freshness'ı GARANTİ EDEMEZ. Bu FAZ
  (Search Resilience v1) freshness sıralaması İNŞA ETMEZ (iş emri madde 10) -- yalnızca
  mevcut `published_date` alanı korunur, ranking/işleme YOK.
- `domains`: SearXNG JSON API'sinde NATIVE bir domain/site filtre parametresi YOKTUR.
  Bu sağlayıcı, yalnızca alttaki motorların (bu kurulumda: google cse, brave, duckduckgo)
  kendi sorgu metni içindeki `site:` operatörünü desteklemesine dayanarak sorgu metnine
  `site:domain` ekler. Bu, benchmark'ta (F -- Domain-Focused Search) 3/3 denemede
  çalıştığı ölçüldü, ama SearXNG'nin kendisinin sağladığı garantili/resmî bir özellik
  DEĞİLDİR -- motor değişirse veya motor site: desteğini kaldırırsa sessizce bozulabilir.
- `limit`: yalnızca bu sağlayıcı tarafında sonuç listesini kırpar (SearXNG kendi başına
  sabit sayıda sonuç döndürür, API üzerinden sayı istenemiyor).

Motor sağlığı ve dayanıklılık (Search Resilience v1 -- bu fazın asıl konusu):

SearXNG yanıtındaki `unresponsive_engines` alanı `SearchOutcome.engines_failed`'e aktarılır.
Önceki fazın benchmarkında, ~25-30 sorgudan oluşan bir patlamadan (burst) sonra google
cse/brave/duckduckgo motorlarının ÜÇÜ DE aynı anda askıya alındığı ve bu durumun kısa bir
süre (>90 saniye) içinde düzelmediği gözlemlendi (bkz. KAIZEN_HEDEF_VE_YOL_HARITASI.md
bölüm 4x/E). Bu FAZDA bu sağlayıcıya şunlar eklendi:

1. **Sınırlı (bounded) yeniden deneme + backoff**: yalnızca GERÇEKTEN geçici hatalarda
   (timeout, HTTP 429, HTTP 5xx, geçici bağlantı hatası) -- bkz. `_classify_*` fonksiyonları
   ve `_RETRYABLE_ERROR_TYPES`. Malformed/beklenmeyen yanıt gibi yeniden denemenin işe
   yaramayacağı durumlar YENİDEN DENENMEZ. Deneme sayısı ve bekleme süresi HER ZAMAN
   sınırlıdır (`max_attempts`, `backoff_base`, `backoff_max`) -- sonsuz döngü YOK, agresif
   sorgu bombardımanı YOK, CAPTCHA/rate-limit bypass YOK (yalnızca makul, sınırlı bekleme).
2. **Burst koruması**: `min_request_interval` ile art arda gelen `search()` çağrıları
   arasına asgari bir bekleme konur (varsayılan 1.0 saniye) -- amaç performans yarışı
   DEĞİL, Kaizen'in kendi patlama davranışıyla SearXNG'nin motorlarını kendi kendine
   askıya aldırmasını önlemek (iş emri madde 5).
3. **Motor bozulması (engine degradation)**: `unresponsive_engines` metadata'ya taşınmaya
   devam eder; ayrıca sonuçlar fiilen TEK bir motordan geliyorsa (`single_engine_dependency`)
   bu da ayrıca işaretlenir (iş emri madde 6).
4. **Provider Health**: her `search()` çağrısından sonra `self.health` (bkz.
   `search.provider.ProviderHealth`) gerçek gözlemlenen sonuca göre güncellenir. Ardışık
   hata sayısı bir eşiği (`unavailable_after`) aşarsa durum UNAVAILABLE'a geçer; bir rate
   limit hatası doğrudan COOLDOWN durumuna ve bir soğuma süresine (`cooldown_until`) yol
   açar -- bu süre boyunca yeni `search()` çağrıları AĞA HİÇ ÇIKMADAN hemen
   `SearchRateLimitedError` fırlatır (burst koruması + rate-limit'e saygı, madde 5/8).
5. **Fallback Contract**: exception'lar asla sessizce boş sonuca çevrilmez (madde 3) --
   her zaman `SearchTimeoutError` / `SearchRateLimitedError` / `SearchUnavailableError` /
   `SearchProviderError` olarak fırlatılır, hepsinin `.status` ve `.fallback_reason`
   alanları vardır. "Sonuç yok ama motor de düşmüş" gibi exception-DIŞI durumlarda ise
   `SearchOutcome.fallback_recommended`/`fallback_reason` doldurulur.

Testlerde GERÇEK bekleme kullanılmaması için `sleep` ve `clock` enjekte edilebilir (bkz.
`tests/test_search_provider.py`), tıpkı `opener`'ın enjekte edilebilir olması gibi.
"""
from __future__ import annotations

import json
import time as _time
import urllib.error
import urllib.parse
import urllib.request

from search.provider import (
    STATUS_DEGRADED,
    STATUS_EMPTY,
    STATUS_OK,
    FALLBACK_REASON_DEGRADED_NO_RESULTS,
    HEALTH_COOLDOWN,
    HEALTH_DEGRADED,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    ProviderHealth,
    SearchDebugInfo,
    SearchOptions,
    SearchOutcome,
    SearchProviderError,
    SearchRateLimitedError,
    SearchResult,
    SearchTimeoutError,
    SearchUnavailableError,
)

DEFAULT_BASE_URL = "http://127.0.0.1:8890"
USER_AGENT = "KaizenAI/1.0 (yerel SearXNG istemcisi; Faz A/B, KaizenBrain'e henuz bagli degil)"
_PDF_EXT = ".pdf"

# Hangi hata sınıfları "genuinely-transient" sayılıp yeniden denenir (iş emri madde 4).
# Not: temel `SearchProviderError` (bozuk JSON, beklenmeyen gövde, 429/5xx dışındaki HTTP
# hataları) BİLEREK bu tuple'da DEĞİL -- bunlar yeniden denenmez, hemen fırlatılır.
_RETRYABLE_ERROR_TYPES = (SearchTimeoutError, SearchRateLimitedError, SearchUnavailableError)


class SearXNGProvider:
    """`SearchProvider` sözleşmesinin SearXNG implementasyonu (yalnız localhost)."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        opener=None,
        max_attempts: int = 3,
        backoff_base: float = 0.2,
        backoff_max: float = 4.0,
        min_request_interval: float = 1.0,
        cooldown_seconds: float = 30.0,
        unavailable_after: int = 3,
        sleep=None,
        clock=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Test edilebilirlik için: gerçek `urllib.request.urlopen` yerine sahte bir opener
        # enjekte edilebilir (bkz. tests/test_search_provider.py) -- böylece testler GERÇEK
        # ağa/SearXNG'ye hiç çıkmaz (iş emri madde 12/18: mock/fixture kullan, gerçek ağa
        # bağımlı test yazma).
        self._opener = opener or urllib.request.urlopen

        # Retry/backoff + burst koruması + health parametreleri (Search Resilience v1).
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_base = max(0.0, backoff_base)
        self.backoff_max = max(self.backoff_base, backoff_max)
        self.min_request_interval = max(0.0, min_request_interval)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self.unavailable_after = max(1, int(unavailable_after))
        # `sleep`/`clock` enjekte edilebilir -- testler GERÇEK zaman geçirmeden backoff/
        # burst-koruması/cooldown davranışını doğrulayabilir (iş emri madde 4: "testler
        # gerçek bekleme kullanmamalı").
        self._sleep = sleep or _time.sleep
        self._clock = clock or _time.monotonic
        self._last_call_at: float | None = None
        self._health = ProviderHealth(state=HEALTH_HEALTHY)
        self._last_search_debug: SearchDebugInfo | None = None

    @property
    def health(self) -> ProviderHealth:
        """Gerçek, gözlemlenmiş sinyallerden inşa edilmiş anlık sağlık durumu (madde 7)."""
        return self._health

    @property
    def last_search_debug(self) -> SearchDebugInfo | None:
        """Son `search()` çağrısının minimal trace/debug metadata'sı (madde 13). Hiç
        `search()` çağrılmadıysa `None`."""
        return self._last_search_debug

    def search(self, query: str, options: SearchOptions | None = None) -> SearchOutcome:
        options = options or SearchOptions()
        if not query or not query.strip():
            outcome = SearchOutcome(results=(), query=query, status=STATUS_EMPTY)
            self._last_search_debug = SearchDebugInfo(
                provider="searxng", query=query, attempt_count=0, elapsed=0.0,
                status=outcome.status, result_count=0, active_engines=(),
                unresponsive_engines=(), fallback_recommended=False, fallback_reason=None,
            )
            return outcome

        self._raise_if_in_cooldown()
        self._respect_min_request_interval()
        self._last_call_at = self._clock()
        _debug_start = self._clock()

        query_text = query
        for domain in options.domains:
            query_text = f"{query_text} site:{domain}"

        params = {"q": query_text, "format": "json"}
        if options.language:
            params["language"] = options.language
        if options.categories:
            params["categories"] = ",".join(options.categories)
        if options.freshness:
            params["time_range"] = options.freshness

        url = f"{self.base_url}/search?{urllib.parse.urlencode(params)}"

        last_error: SearchProviderError | None = None
        for attempt in range(1, self.max_attempts + 1):
            request = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
            )
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    raw = response.read()
            except urllib.error.HTTPError as exc:
                last_error = _classify_http_error(exc)
                if self._should_retry(last_error, attempt):
                    self._sleep(self._backoff_delay(attempt))
                    continue
                self._record_failure(last_error)
                self._record_debug_for_error(query, last_error, attempt, _debug_start)
                raise last_error from exc
            except (urllib.error.URLError, OSError) as exc:
                last_error = _classify_connection_error(exc)
                if self._should_retry(last_error, attempt):
                    self._sleep(self._backoff_delay(attempt))
                    continue
                self._record_failure(last_error)
                self._record_debug_for_error(query, last_error, attempt, _debug_start)
                raise last_error from exc

            # HTTP seviyesinde başarılı yanıt geldi -- JSON ayrıştırma hataları yeniden
            # DENENMEZ (aynı bozuk gövdeyi tekrar tekrar istemek sonucu değiştirmez).
            try:
                payload = json.loads(raw.decode("utf-8", errors="replace"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                err = SearchProviderError(f"SearXNG bozuk JSON dondurdu: {exc}")
                self._record_failure(err)
                self._record_debug_for_error(query, err, attempt, _debug_start)
                raise err from exc

            if not isinstance(payload, dict):
                err = SearchProviderError("SearXNG beklenmeyen yanit govdesi dondurdu (dict degil)")
                self._record_failure(err)
                self._record_debug_for_error(query, err, attempt, _debug_start)
                raise err

            outcome = _build_outcome(payload, query, options)
            self._record_success(outcome)
            active_engines = tuple(sorted({e for r in outcome.results for e in r.engines}))
            self._last_search_debug = SearchDebugInfo(
                provider="searxng", query=query, attempt_count=attempt,
                elapsed=self._clock() - _debug_start, status=outcome.status,
                result_count=len(outcome.results), active_engines=active_engines,
                unresponsive_engines=outcome.engines_failed,
                fallback_recommended=outcome.fallback_recommended,
                fallback_reason=outcome.fallback_reason,
            )
            return outcome

        # Buraya normalde ulaşılmaz (döngü ya `return` ya da `raise` ile biter); yine de
        # bir güvenlik ağı olarak son bilinen hatayı fırlat.
        if last_error is not None:
            self._record_failure(last_error)
            self._record_debug_for_error(query, last_error, self.max_attempts, _debug_start)
            raise last_error
        raise SearchProviderError("SearXNG: bilinmeyen hata (deneme dongusu tamamlanamadi)")

    def _record_debug_for_error(
        self, query: str, error: SearchProviderError, attempt_count: int, start: float
    ) -> None:
        self._last_search_debug = SearchDebugInfo(
            provider="searxng", query=query, attempt_count=attempt_count,
            elapsed=self._clock() - start, status=error.status, result_count=0,
            active_engines=(), unresponsive_engines=(), fallback_recommended=True,
            fallback_reason=error.fallback_reason,
        )

    # -- Burst koruması --------------------------------------------------------------

    def _respect_min_request_interval(self) -> None:
        if self.min_request_interval <= 0 or self._last_call_at is None:
            return
        elapsed = self._clock() - self._last_call_at
        remaining = self.min_request_interval - elapsed
        if remaining > 0:
            self._sleep(remaining)

    # -- Rate-limit sonrası soğuma (cooldown) -- burst korumasıyla birlikte çalışır -----

    def _raise_if_in_cooldown(self) -> None:
        if self._health.state != HEALTH_COOLDOWN or self._health.cooldown_until is None:
            return
        now = self._clock()
        remaining = self._health.cooldown_until - now
        if remaining > 0:
            err = SearchRateLimitedError(
                "SearXNG onceki hiz siniri nedeniyle soguma suresinde; "
                "istek gonderilmedi (burst korumasi)",
                retry_after=remaining,
            )
            self._last_search_debug = SearchDebugInfo(
                provider="searxng", query="", attempt_count=0, elapsed=0.0,
                status=err.status, result_count=0, active_engines=(),
                unresponsive_engines=(), fallback_recommended=True,
                fallback_reason=err.fallback_reason,
            )
            raise err

    # -- Retry/backoff -----------------------------------------------------------------

    def _should_retry(self, error: SearchProviderError, attempt: int) -> bool:
        if attempt >= self.max_attempts:
            return False
        return isinstance(error, _RETRYABLE_ERROR_TYPES)

    def _backoff_delay(self, attempt: int) -> float:
        delay = self.backoff_base * (2 ** (attempt - 1))
        return min(delay, self.backoff_max)

    # -- Provider Health (madde 7) -------------------------------------------------------

    def _record_success(self, outcome: SearchOutcome) -> None:
        state = HEALTH_DEGRADED if outcome.status == STATUS_DEGRADED else HEALTH_HEALTHY
        self._health = ProviderHealth(
            state=state,
            consecutive_failures=0,
            last_status=outcome.status,
            last_error=None,
            last_success_at=self._clock(),
            last_failure_at=self._health.last_failure_at,
            cooldown_until=None,
        )

    def _record_failure(self, error: SearchProviderError) -> None:
        now = self._clock()
        consecutive = self._health.consecutive_failures + 1
        cooldown_until = None
        if isinstance(error, SearchRateLimitedError):
            wait = error.retry_after if error.retry_after and error.retry_after > 0 else self.cooldown_seconds
            cooldown_until = now + wait
            state = HEALTH_COOLDOWN
        elif consecutive >= self.unavailable_after:
            state = HEALTH_UNAVAILABLE
        else:
            state = HEALTH_DEGRADED
        self._health = ProviderHealth(
            state=state,
            consecutive_failures=consecutive,
            last_status=error.status,
            last_error=str(error),
            last_success_at=self._health.last_success_at,
            last_failure_at=now,
            cooldown_until=cooldown_until,
        )


# --- Hata sınıflandırma (retryable vs non-retryable, iş emri madde 4) -------------------


def _classify_http_error(exc: urllib.error.HTTPError) -> SearchProviderError:
    code = exc.code
    if code == 429:
        return SearchRateLimitedError(
            f"SearXNG hiz sinirina takildi (HTTP 429)", retry_after=_parse_retry_after(exc)
        )
    if code in (500, 502, 503):
        return SearchUnavailableError(f"SearXNG sunucu hatasi (HTTP {code})")
    # Diğer 4xx/5xx (400, 401, 403, 404, 504 vb.) -- yeniden denemenin işe yaramayacağı,
    # genellikle kalıcı bir istemci/uç nokta hatası. Bilerek retryable DEĞİL.
    return SearchProviderError(f"SearXNG HTTP hatasi: {code}")


def _classify_connection_error(exc: BaseException) -> SearchProviderError:
    reason = getattr(exc, "reason", None)
    if isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError):
        return SearchTimeoutError(f"SearXNG zaman asimina ugradi: {exc}")
    return SearchUnavailableError(f"SearXNG'ye erisilemedi: {exc}")


def _parse_retry_after(exc: urllib.error.HTTPError) -> float | None:
    try:
        headers = getattr(exc, "headers", None)
        value = headers.get("Retry-After") if headers else None
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# --- Sonuç normalizasyonu + status/fallback/health sinyalleri (madde 3/6/8) -------------


def _build_outcome(payload: dict, query: str, options: SearchOptions) -> SearchOutcome:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raw_results = []

    engines_failed = tuple(
        (str(item[0]), str(item[1]))
        for item in (payload.get("unresponsive_engines") or [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    )

    results = []
    seen_urls = set()
    contributing_engines: set[str] = set()
    for item in raw_results:
        if not isinstance(item, dict):
            continue  # bozuk/malformed sonuç -- sessizce atla, tüm cevabı bozma
        url_value = item.get("url")
        if not url_value or not isinstance(url_value, str):
            continue
        if url_value in seen_urls:
            continue  # aynı URL birden fazla motordan gelebilir -- yinelenenleri at
        seen_urls.add(url_value)
        normalized = _normalize(item, query)
        results.append(normalized)
        contributing_engines.update(normalized.engines)
        if len(results) >= max(options.limit, 0):
            break

    degraded = bool(engines_failed)
    # İş emri madde 6: sonuçlar geldi ama fiilen TEK bir motordan geliyorsa bunu da
    # "degraded" sinyaline dahil et -- gerçek veriden hesaplanır (LLM tahmini YOK).
    single_engine_dependency = bool(results) and len(contributing_engines) == 1

    if not results:
        if engines_failed:
            # İş emri madde 8'in tam olarak modellediği senaryo: "sonuç yok" ile "sistem
            # düşmüş" karıştırılmamalı -- burada ikisi de doğru olabilir, bu yüzden hem
            # degraded=True/status=DEGRADED hem de fallback_recommended=True işaretlenir.
            status = STATUS_DEGRADED
            fallback_recommended = True
            fallback_reason = FALLBACK_REASON_DEGRADED_NO_RESULTS
        else:
            # Motor hatası YOK, gerçekten alakalı sonuç bulunamadı -- sistem çalışıyor.
            status = STATUS_EMPTY
            fallback_recommended = False
            fallback_reason = None
    elif degraded or single_engine_dependency:
        status = STATUS_DEGRADED
        # Kullanılabilir sonuç zaten var -- üst katmana "fallback ZORUNLU" denmiyor, ama
        # `degraded`/`single_engine_dependency` alanlarından bunu görüp isterse kendi
        # kararını (ör. ek bir Hermes doğrulaması) verebilir.
        fallback_recommended = False
        fallback_reason = None
    else:
        status = STATUS_OK
        fallback_recommended = False
        fallback_reason = None

    return SearchOutcome(
        results=tuple(results),
        query=query,
        engines_failed=engines_failed,
        degraded=degraded,
        status=status,
        single_engine_dependency=single_engine_dependency,
        fallback_recommended=fallback_recommended,
        fallback_reason=fallback_reason,
    )


def _normalize(item: dict, query: str) -> SearchResult:
    url_value = item.get("url") or ""
    engines = item.get("engines")
    if not isinstance(engines, (list, tuple)):
        single = item.get("engine")
        engines = [single] if single else []
    domain = urllib.parse.urlparse(url_value).hostname or ""
    path_only = url_value.lower().split("?")[0].split("#")[0]
    is_pdf = path_only.endswith(_PDF_EXT) or item.get("content_type") == "application/pdf"
    score = item.get("score")
    if not isinstance(score, (int, float)):
        score = None
    return SearchResult(
        title=str(item.get("title") or ""),
        url=url_value,
        snippet=str(item.get("content") or ""),
        engine=str(item.get("engine") or (engines[0] if engines else "")),
        engines=tuple(str(e) for e in engines),
        category=str(item.get("category") or ""),
        score=score,
        published_date=item.get("publishedDate") or None,
        domain=domain,
        is_pdf=bool(is_pdf),
        query=query,
    )
