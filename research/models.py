"""KAIZEN Research Engine — sözleşmeler (İş Emri #2 madde 8/17/26-27).

Bu dosya SAF VERİ modelleridir — hiçbir ağ/model/dosya çağrısı yapmaz (madde 61: tek
dev sınıf yasağı burada da geçerli, ama bu modül zaten sınıf bile değil, yalnız
dataclass + sabitler). Her alan İş Emri #2'nin ilgili maddesine karşılık gelir; tam
gerekçe için `docs/RESEARCH_ENGINE.md`'ye bakınız.

KRİTİK AYRIM (madde 13, docs/RESEARCH_ENGINE.md §4'te tekrar edilir): Search ≠ Evidence
≠ Fact ≠ Principle ≠ Experience. Bu dosyadaki hiçbir durum sabiti "VERIFIED" DEĞİLDİR --
o etiket yalnızca `core/trace.py`'nin kesin-araç/parametre-defteri rotasına aittir.
Research Engine bir cevabı EN FAZLA `SUPPORTED` güvenine taşıyabilir (bugünkü
`memory_grounded` rotasıyla aynı tavan)."""
from dataclasses import dataclass, field
from typing import Optional, Tuple


class ResearchModelError(ValueError):
    """Bir Research Engine sözleşmesi geçersiz durumda inşa edilmeye çalışıldığında."""


# --- ResearchResult durum sözleşmesi (madde 27) ------------------------------------
SUPPORTED = "SUPPORTED"
PARTIAL = "PARTIAL"
CONFLICTED = "CONFLICTED"
INSUFFICIENT = "INSUFFICIENT"
SEARCH_DEGRADED = "SEARCH_DEGRADED"
SEARCH_UNAVAILABLE = "SEARCH_UNAVAILABLE"

RESULT_STATUSES = (
    SUPPORTED, PARTIAL, CONFLICTED, INSUFFICIENT, SEARCH_DEGRADED, SEARCH_UNAVAILABLE,
)

# --- Evidence.fetch_status (madde 13/17: arama sonucu != kanıt != fact) -------------
FETCH_OK = "FETCH_OK"
FETCH_SNIPPET_ONLY = "FETCH_SNIPPET_ONLY"  # yalnız arama sonucu (title/url/snippet), hiç getirilmedi
FETCH_BLOCKED_ROBOTS = "FETCH_BLOCKED_ROBOTS"
FETCH_BLOCKED_SSRF = "FETCH_BLOCKED_SSRF"
FETCH_TIMEOUT = "FETCH_TIMEOUT"
FETCH_TOO_LARGE = "FETCH_TOO_LARGE"
FETCH_HTTP_ERROR = "FETCH_HTTP_ERROR"
FETCH_MALFORMED = "FETCH_MALFORMED"

FETCH_STATUSES = (
    FETCH_OK, FETCH_SNIPPET_ONLY, FETCH_BLOCKED_ROBOTS, FETCH_BLOCKED_SSRF,
    FETCH_TIMEOUT, FETCH_TOO_LARGE, FETCH_HTTP_ERROR, FETCH_MALFORMED,
)

# Kanıtı GERÇEKTEN getirip okuduğumuz durumlar (madde 36: "snippet-only bir sonuç ASLA
# VERIFIED olamaz" -- bu kümenin dışındaki her şey, tanım gereği "yalnızca arama sonucu").
FETCH_STATUSES_WITH_REAL_CONTENT = (FETCH_OK,)

# --- Kaynak otoritesi (madde 18 -- accounting/source_registry.py'nin priority'sinden
#     TÜRETİLİR, PARALEL bir liste DEĞİLDİR; bkz. research/evidence.py) -------------
OFFICIAL = "OFFICIAL"
PROFESSIONAL = "PROFESSIONAL"
SECONDARY = "SECONDARY"
UNKNOWN_SOURCE = "UNKNOWN"

SOURCE_TYPES = (OFFICIAL, PROFESSIONAL, SECONDARY, UNKNOWN_SOURCE)

# --- Evidence.confidence (bir FACT güveni DEĞİL -- yalnız "bu kanıt parçası ne kadar
#     kullanılabilir" proxy'si; asla core/trace.py'nin VERIFIED/SUPPORTED etiketleriyle
#     karıştırılmaz) --------------------------------------------------------------
EVIDENCE_LOW = "LOW"
EVIDENCE_MEDIUM = "MEDIUM"
EVIDENCE_HIGH = "HIGH"

EVIDENCE_CONFIDENCE_LEVELS = (EVIDENCE_LOW, EVIDENCE_MEDIUM, EVIDENCE_HIGH)

# --- Evidence classification (Passage-level fact classification) ----------
EVIDENCE_FACT = "FACT"
EVIDENCE_HYPOTHETICAL = "HYPOTHETICAL"
EVIDENCE_EXAMPLE = "EXAMPLE"
EVIDENCE_FORECAST = "FORECAST"
EVIDENCE_OUT_OF_PERIOD = "OUT_OF_PERIOD"
EVIDENCE_UNKNOWN = "UNKNOWN"

EVIDENCE_CLASSIFICATIONS = (
    EVIDENCE_FACT, EVIDENCE_HYPOTHETICAL, EVIDENCE_EXAMPLE,
    EVIDENCE_FORECAST, EVIDENCE_OUT_OF_PERIOD, EVIDENCE_UNKNOWN
)

# Negative signal keywords for hypothetical/example content
EVIDENCE_NEGATIVE_SIGNALS = (
    "varsayımsal", "varsayılmıştır", "varsayım", "örnek", "örneğin",
    "örnek hesaplama", "hesaplama örneği", "senaryo", "simülasyon",
    "tahmini", "tahmin", "öngörü", "farazi", "temsili",
    "örnek amaçlı", "taslak", "üzerinden hesaplanmıştır",
    "kabul edilmiştir"
)

# Positive signal keywords for factual content (Turkish stem matching)
EVIDENCE_POSITIVE_SIGNALS = (
    "belirlen", "açıklan", "geçerlidir", "uygulanacaktır",
    "yürürlük", "itibaren geçerli", "karar", "tebliğ",
    "ilan edil", "yayınlan", "resmi", "resmen", "resmi",
    "tespit edil", "açıklan", "belirlendi", "açıklandı"
)


@dataclass(frozen=True)
class Subquestion:
    """Tek bir alt-soru + ona karşılık gelen arama sorgusu (madde 9-10). Planlayıcı
    (research/planner.py) BURADA hiçbir oran/tutar/tarih/mevzuat SONUCU üretmez --
    yalnızca NEYİN araştırılacağına karar verir."""
    text: str
    search_query: str
    accounting_topic: str = ""

    def __post_init__(self):
        if not self.text.strip():
            raise ResearchModelError("Subquestion.text boş olamaz")
        if not self.search_query.strip():
            raise ResearchModelError("Subquestion.search_query boş olamaz")


@dataclass(frozen=True)
class ResearchPlan:
    """Bir kullanıcı sorusunun araştırma planı (madde 9-10)."""
    question: str
    subquestions: Tuple[Subquestion, ...]
    requested_period: Optional[str] = None  # ör. "2026" -- soru güncel bir yılı ima ediyorsa

    def __post_init__(self):
        if not self.question.strip():
            raise ResearchModelError("ResearchPlan.question boş olamaz")
        if not self.subquestions:
            raise ResearchModelError("ResearchPlan.subquestions boş olamaz (en az 1 alt-soru)")


@dataclass(frozen=True)
class Evidence:
    """Tek bir kanıt parçası (madde 17). ÖNEMLİ: bu bir FACT DEĞİLDİR -- yalnızca
    "şu URL'de, şu tarihte, şu pasaj görüldü" kaydıdır. Bir Evidence'ın "fact" haline
    gelip gelemeyeceğine `research/verifier.py` (+ `accounting/consensus.py`) karar
    verir, bu dataclass'ın kendisi DEĞİL."""
    evidence_id: str
    query: str
    subquestion: str
    url: str
    domain: str
    source_name: str
    source_type: str  # OFFICIAL/PROFESSIONAL/SECONDARY/UNKNOWN
    title: str
    published_at: Optional[str]  # içerikten çıkarılan tarih; bulunamazsa None (madde 20: UYDURULMAZ)
    retrieved_at: str  # bu araştırmanın çalıştığı an (ISO -- ne zaman bulunduğu, ne zaman yayınlandığı DEĞİL)
    passage: str  # kullanılan asıl metin pasajı (madde 16: sayfanın TAMAMI değil)
    extracted_claim: str  # pasajdan çıkarılan iddia cümlesi (madde 22)
    value: Optional[str] = None
    unit: Optional[str] = None
    period: Optional[str] = None  # bu kanıtın ait olduğu dönem/yıl (madde 20-21)
    accounting_topic: str = ""
    official: bool = False
    confidence: str = EVIDENCE_LOW
    search_provider: str = ""
    fetch_status: str = FETCH_OK
    classification: str = EVIDENCE_UNKNOWN  # FACT, HYPOTHETICAL, EXAMPLE, FORECAST, OUT_OF_PERIOD, UNKNOWN

    def __post_init__(self):
        if not self.url.strip():
            raise ResearchModelError("Evidence.url boş olamaz")
        if self.source_type not in SOURCE_TYPES:
            raise ResearchModelError(f"Evidence.source_type geçersiz: {self.source_type!r}")
        if self.confidence not in EVIDENCE_CONFIDENCE_LEVELS:
            raise ResearchModelError(f"Evidence.confidence geçersiz: {self.confidence!r}")
        if self.fetch_status not in FETCH_STATUSES:
            raise ResearchModelError(f"Evidence.fetch_status geçersiz: {self.fetch_status!r}")
        if self.official and self.source_type != OFFICIAL:
            raise ResearchModelError(
                "Evidence.official=True ama source_type OFFICIAL değil -- tutarsız durum"
            )
        if self.classification not in EVIDENCE_CLASSIFICATIONS:
            raise ResearchModelError(f"Evidence.classification geçersiz: {self.classification!r}")

    def has_real_content(self):
        """madde 36: yalnız arama sonucu (title/url/snippet) mi, yoksa gerçekten
        getirilip okundu mu (FETCH_OK)?"""
        return self.fetch_status in FETCH_STATUSES_WITH_REAL_CONTENT

    def is_fact_evidence(self):
        """Bu evidence FACT sınıfında mı? (consensus'a katılabilir mi?)"""
        return self.classification == EVIDENCE_FACT and self.has_real_content()


@dataclass(frozen=True)
class Claim:
    """Bir veya birden fazla Evidence'tan çıkarılan, henüz uzlaşıya (consensus)
    sokulmamış tek bir iddia (madde 22). `research/verifier.py` bunu
    `accounting/consensus.py`'ye göndererek nihai durumunu belirler."""
    text: str
    value: Optional[str]
    period: Optional[str]
    supporting_evidence_ids: Tuple[str, ...]
    status: str  # SUPPORTED | PARTIAL | CONFLICTED | INSUFFICIENT (asla VERIFIED)

    def __post_init__(self):
        if not self.text.strip():
            raise ResearchModelError("Claim.text boş olamaz")
        if self.status not in RESULT_STATUSES:
            raise ResearchModelError(f"Claim.status geçersiz: {self.status!r}")
        if self.status == "VERIFIED":  # asla ulaşılamaz ama açıkça kilitlenir
            raise ResearchModelError("Claim.status asla VERIFIED olamaz (madde 13)")
        if not self.supporting_evidence_ids:
            raise ResearchModelError("Claim en az bir Evidence'a dayanmalı (kaynaksız iddia yasak)")


@dataclass(frozen=True)
class ResearchResult:
    """Bir araştırma turunun TAM sonucu (madde 26). `KaizenBrain`'e (ileride, Faz 28'de)
    bu nesne döner -- asla ham arama sonucu, asla ham Hermes metni."""
    status: str
    question: str
    subquestions: Tuple[str, ...]
    queries: Tuple[str, ...]
    search_health: str  # search/provider.py'nin STATUS_* sözleşmesiyle uyumlu (OK/DEGRADED/vb.)
    evidence: Tuple[Evidence, ...] = ()
    claims: Tuple[Claim, ...] = ()
    verified_claims: Tuple[Claim, ...] = ()
    conflicts: Tuple[str, ...] = ()
    missing_information: Tuple[str, ...] = ()
    sources: Tuple[str, ...] = ()
    elapsed_time: float = 0.0

    def __post_init__(self):
        if self.status not in RESULT_STATUSES:
            raise ResearchModelError(f"ResearchResult.status geçersiz: {self.status!r}")
        for claim in self.verified_claims:
            if claim not in self.claims:
                raise ResearchModelError(
                    "ResearchResult.verified_claims, claims'in bir ALT KÜMESİ olmalı"
                )
        # madde 36: snippet-only bir Evidence hiçbir zaman TEK BAŞINA bir claim'i
        # 'SUPPORTED' yapamaz -- bu invariant burada, ResearchResult bütünlüğünde
        # kontrol edilir (verifier.py claim üretirken de aynı kuralı uygular, madde 61
        # "iki yerde aynı kural" -- savunma katmanları çakışmaz, birbirini kanıtlar).
        evidence_by_id = {e.evidence_id: e for e in self.evidence}
        for claim in self.verified_claims:
            supporting = [evidence_by_id[eid] for eid in claim.supporting_evidence_ids
                          if eid in evidence_by_id]
            if supporting and not any(e.has_real_content() for e in supporting):
                raise ResearchModelError(
                    f"Claim {claim.text!r} yalnizca snippet-only kanitlarla VERIFIED/"
                    "SUPPORTED sayilamaz (madde 36)"
                )
