"""Kaizen'in arama motorlarından bağımsız SearchProvider sözleşmesi (iş emri Faz B).

Amaç: Kaizen'in gelecekte SearXNG, Hermes, başka ücretsiz/yerel bir sağlayıcı veya
profesyonel bir API arasında geçiş yapabilmesi. KaizenBrain (veya herhangi bir çağıran
kod) asla `SearXNGProvider` gibi somut bir sınıfa ya da `searxng.search()` gibi bir
çağrıya DOĞRUDAN bağlanmamalı -- yalnızca bu modüldeki `SearchProvider` sözleşmesine
(Protocol) bağlanmalıdır.

ÖNEMLİ (iş emri sınırı, madde 15): Bu modül KaizenBrain'e BAĞLANMAZ. Yalnızca bağımsız,
test edilebilir bir katmandır. Search != Research (madde 16): bu sözleşme yalnızca aday
kaynakları BULUR (source discovery) -- sayfa içeriğini indirmek (fetch), temizlemek,
soruyla ilgili bölümü seçmek (retrieval) ve kaynakları karşılaştırıp güven durumu
belirlemek (consensus/verifier) bu katmanın işi DEĞİLDİR; bu adımlar zaten Kaizen'de
ayrı ayrı var (`accounting/crawler.py`, `accounting/consensus.py`, `core/kaizen_brain.py`)
ve bu iş emri kapsamında değiştirilmedi.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------------------
# Search Status Contract (iş emri "Search Resilience v1", madde 2-3).
#
# `core/trace.py`'nin kendi konvansiyonuna uyularak (Enum değil, düz string sabitleri +
# bir "tüm geçerli değerler" tuple'ı) tasarlandı. Amaç: "sonuç yok" ile "arama sistemi
# çalışmıyor" durumlarını KESİNLİKLE karıştırmamak.
#
#   OK            -- en az bir sonuç geldi, motor sorunu gözlenmedi.
#   EMPTY         -- sorgu geçerliydi, sağlayıcı yanıt verdi, ama gerçekten sonuç yok
#                    (motor hatası YOK -- bu "sistem çalışıyor, konuyla ilgili bir şey
#                    bulamadı" demektir).
#   DEGRADED      -- sonuç geldi (veya hiç gelmedi) AMA bir/birden fazla motor düşük veya
#                    sonuçlar fiilen tek bir motora bağımlı (bkz. single_engine_dependency).
#   RATE_LIMITED  -- sağlayıcı "çok fazla istek" nedeniyle isteği reddetti (HTTP 429 vb.)
#                    veya provider zaten bilinen bir soğuma (cooldown) süresinde.
#   TIMEOUT       -- istek zaman aşımına uğradı (retry'lardan sonra bile).
#   UNAVAILABLE   -- sağlayıcıya hiç erişilemedi (bağlantı hatası, 5xx) veya art arda çok
#                    sayıda hata nedeniyle "kullanılamaz" olarak işaretlendi.
#   ERROR         -- yukarıdakilerin hiçbirine net biçimde uymayan, sağlayıcı seviyesinde
#                    kurtarılamayan başka bir hata (bozuk JSON, beklenmeyen gövde, vb.)
#
# KRİTİK KURAL: bu durumlardan RATE_LIMITED / TIMEOUT / UNAVAILABLE / ERROR asla sessizce
# `SearchOutcome(results=())`'a dönüştürülmez -- bunlar her zaman tipli bir exception
# (aşağıya bakınız) olarak FIRLATILIR. Yalnızca OK / EMPTY / DEGRADED, `search()`'ün normal
# (exception fırlatmayan) dönüş değeri olan `SearchOutcome.status` alanında görünür.
STATUS_OK = "OK"
STATUS_EMPTY = "EMPTY"
STATUS_DEGRADED = "DEGRADED"
STATUS_RATE_LIMITED = "RATE_LIMITED"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_ERROR = "ERROR"
SEARCH_STATUSES = (
    STATUS_OK, STATUS_EMPTY, STATUS_DEGRADED, STATUS_RATE_LIMITED,
    STATUS_TIMEOUT, STATUS_UNAVAILABLE, STATUS_ERROR,
)

# ---------------------------------------------------------------------------------------
# Fallback Contract (iş emri madde 8). Üst katmanın "fallback önerilir" sinyalini ALDIĞINDA
# SEBEBİNİ kaybetmemesi için: hem exception'larda (`.fallback_reason` class attr) hem de
# `SearchOutcome.fallback_reason` alanında aynı sabitler kullanılır. Bu FAZDA otomatik bir
# canlı Hermes fallback bağlantısı YAPILMAZ (madde 8) -- yalnızca sözleşme/sinyal.
FALLBACK_REASON_RATE_LIMITED = "rate_limited"
FALLBACK_REASON_TIMEOUT = "timeout"
FALLBACK_REASON_UNAVAILABLE = "unavailable"
FALLBACK_REASON_DEGRADED_NO_RESULTS = "degraded_no_results"
FALLBACK_REASON_ERROR = "error"

# ---------------------------------------------------------------------------------------
# Provider Health (iş emri madde 7). Gerçek, gözlemlenebilir sinyallerden inşa edilir (LLM
# tahmini YOK): son N denemenin başarı/başarısızlık durumu, varsa bilinen soğuma süresi.
HEALTH_HEALTHY = "HEALTHY"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_COOLDOWN = "COOLDOWN"
HEALTH_UNAVAILABLE = "UNAVAILABLE"
PROVIDER_HEALTH_STATES = (HEALTH_HEALTHY, HEALTH_DEGRADED, HEALTH_COOLDOWN, HEALTH_UNAVAILABLE)


@dataclass(frozen=True)
class SearchDebugInfo:
    """Tek bir `search()` çağrısı için minimal gözlemlenebilirlik/trace metadata'sı
    (iş emri "Search Resilience v1", madde 13).

    `core/trace.py`'deki `KaizenTrace` ile AYNI konvansiyon izlenir: çağrıdan SONRA okunur
    (bkz. `SearXNGProvider.last_search_debug`), döndürülen `SearchOutcome`'u ya da fırlatılan
    exception'ı hiçbir şekilde DEĞİŞTİRMEZ -- salt gözlem amaçlıdır. Bu FAZDA KaizenBrain'in
    kendi trace zincirine bağlanması GEREKMİYOR (madde 13/14): bu, bağımsız/isteğe bağlı bir
    katmandır.
    """

    provider: str
    query: str
    attempt_count: int
    elapsed: float
    status: str
    result_count: int
    active_engines: tuple[str, ...]
    unresponsive_engines: tuple[tuple[str, str], ...]
    fallback_recommended: bool
    fallback_reason: str | None


@dataclass(frozen=True)
class ProviderHealth:
    """Bir `SearchProvider`'ın o anki sağlık anlık görüntüsü (snapshot).

    Gelecekte bir Research Engine'in "SearXNG sağlıklı mı / degraded mı / cooldown'da mı /
    kullanılamaz mı" sorusunu LLM'e sormadan, doğrudan bu nesneden cevaplayabilmesi için
    tasarlandı (iş emri madde 7). Sağlayıcı her `search()` çağrısından sonra kendi dahili
    `ProviderHealth`'ini bu gerçek sonuca göre günceller (bkz. `SearXNGProvider._record_success`
    / `_record_failure`).
    """

    state: str = HEALTH_HEALTHY
    consecutive_failures: int = 0
    last_status: str = STATUS_OK
    last_error: str | None = None
    last_success_at: float | None = None
    last_failure_at: float | None = None
    cooldown_until: float | None = None


@dataclass(frozen=True)
class SearchOptions:
    """SearchProvider.search() için minimum, sağlayıcı-bağımsız seçenekler.

    Her alan yalnızca ALTTAKİ sağlayıcı gerçekten destekliyorsa etkilidir. Bir sağlayıcı
    desteklemediği bir seçeneği sessizce yok sayabilir ama destekliyormuş gibi
    davranamaz -- hangi alanın somut sağlayıcıda gerçek/native, hangisinin en-iyi-çaba
    (best-effort) ya da dolaylı (workaround) olduğu o sağlayıcının kendi docstring'inde
    açıkça belirtilir (bkz. `searxng_provider.py`).
    """

    limit: int = 10
    domains: tuple[str, ...] = ()
    freshness: str | None = None  # ör. "day" | "week" | "month" | "year"
    language: str = "tr"
    categories: tuple[str, ...] = ("general",)


@dataclass(frozen=True)
class SearchResult:
    """Sağlayıcıdan bağımsız, normalize edilmiş tek arama sonucu (iş emri madde 10)."""

    title: str
    url: str
    snippet: str
    engine: str
    engines: tuple[str, ...]
    category: str
    score: float | None
    published_date: str | None
    domain: str
    is_pdf: bool
    query: str


class SearchProviderError(Exception):
    """Sağlayıcı seviyesinde kurtarılamayan hata (ağ, zaman aşımı, bozuk yanıt).

    İş emri madde 3'ün kritik kuralı: bu ve alt sınıfları asla sessizce boş bir
    `SearchOutcome`'a çevrilmez -- her zaman fırlatılır (raise). Alt sınıflar (aşağıda),
    çağıran kodun `except SearchProviderError` ile eskisi gibi genel yakalama yapabilmesini
    KORURKEN (geriye dönük uyumluluk), `.status` ve `.fallback_reason` üzerinden daha
    ayrıntılı sınıflandırma sunar -- böylece üst katman mesaj metnini ayrıştırmak
    (string parsing) zorunda kalmaz.
    """

    status = STATUS_ERROR
    fallback_reason = FALLBACK_REASON_ERROR


class SearchTimeoutError(SearchProviderError):
    """İstek, (varsa) yeniden denemelerden sonra bile zaman aşımına uğradı."""

    status = STATUS_TIMEOUT
    fallback_reason = FALLBACK_REASON_TIMEOUT


class SearchRateLimitedError(SearchProviderError):
    """Sağlayıcı hız sınırına takıldı (HTTP 429) ya da provider zaten bilinen bir soğuma
    (cooldown) süresindeydi (bkz. `SearXNGProvider`'ın burst-koruması).

    `retry_after`: sağlayıcının bildirdiği (varsa `Retry-After` header'ı) veya dahili
    cooldown hesaplamasından gelen, saniye cinsinden tahmini bekleme süresi. Bilinmiyorsa
    `None` -- üst katman KENDİ makul varsayılanını kullanmalı, burada uydurulmaz.
    """

    status = STATUS_RATE_LIMITED
    fallback_reason = FALLBACK_REASON_RATE_LIMITED

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class SearchUnavailableError(SearchProviderError):
    """Sağlayıcıya hiç erişilemedi (bağlantı hatası, 5xx) veya art arda çok sayıda hata
    nedeniyle sağlayıcı "kullanılamaz" durumuna geçti."""

    status = STATUS_UNAVAILABLE
    fallback_reason = FALLBACK_REASON_UNAVAILABLE


@dataclass(frozen=True)
class SearchOutcome:
    """search() çağrısının tam sonucu: sonuçlar + motor sağlığı + fallback sinyali.

    İş emri madde 9: "Bir motorun hata vermesi bütün SearXNG sistemini başarısız
    saydırmamalı. Ama sistem tek bir motora fiilen bağımlı hale gelmişse bunu açıkça
    raporlamalı." -- `engines_failed` ve `degraded` bu gözlemlenebilirliği sağlar; çağıran
    kod `results` boş olmasa bile `degraded=True` ise (bazı motorlar düşmüş) bunu
    loglayabilir/raporlayabilir.

    Yeni alanlar (iş emri "Search Resilience v1", madde 3/6/8) -- hepsi varsayılan değerli,
    yani MEVCUT testler/çağıran kod bu alanları hiç bilmeden de bu sınıfı kullanmaya devam
    edebilir (geriye dönük uyumluluk kasıtlı olarak korunmuştur):

    - `status`: yalnızca OK / EMPTY / DEGRADED olabilir (RATE_LIMITED/TIMEOUT/UNAVAILABLE/
      ERROR durumları her zaman exception olarak fırlatılır, bu alanda GÖRÜNMEZ).
    - `single_engine_dependency`: sonuçlar geldi ama fiilen TEK bir motordan geldiyse True
      (iş emri madde 6 -- "sonuçlar fiilen tek motora bağımlı" sinyali, gerçek veriden
      hesaplanır, tahmin YOK).
    - `fallback_recommended` / `fallback_reason`: yalnızca exception fırlatılMADAN dönen
      ama kullanılabilir sonuç üretemeyen durumlar için (örn. tüm motorlar düşmüş ve sonuç
      sıfır) -- exception durumunda aynı bilgi exception'ın kendi `.fallback_reason`'ında
      bulunur (iş emri madde 8: "fallback sebebi kaybolmamalı").
    """

    results: tuple[SearchResult, ...]
    query: str
    engines_failed: tuple[tuple[str, str], ...] = ()  # (motor_adi, sebep)
    degraded: bool = False
    status: str = STATUS_OK
    single_engine_dependency: bool = False
    fallback_recommended: bool = False
    fallback_reason: str | None = None


@runtime_checkable
class SearchProvider(Protocol):
    """Kaizen'in bağlanacağı TEK sözleşme. SearXNG, Hermes, başka bir sağlayıcı -- hepsi
    bunu uygular; çağıran kod hiçbirinin somut sınıfını bilmek zorunda değildir.

    Not (iş emri "Search Resilience v1"): bu Protocol KASITLI OLARAK minimal tutuldu --
    yalnızca `search()` zorunludur. Bir sağlayıcı isteğe bağlı olarak `.health ->
    ProviderHealth` gibi ek bir yetenek sunabilir (bkz. `SearXNGProvider.health`), ama bu
    sözleşmenin gerekli bir parçası DEĞİLDİR; çağıran kod `getattr(provider, "health",
    None)` ile güvenli biçimde kontrol etmelidir.
    """

    def search(self, query: str, options: SearchOptions | None = None) -> SearchOutcome:
        ...
