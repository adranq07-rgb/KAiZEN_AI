"""KAIZEN — Deneyimin STRATEJİ meta-verisi (Experience'ın 10 alanlık D1/D2 kontratını
DEĞİŞTİRMEDEN, yanında duran ayrı bir kayıt).

`learning/experience_model.py::Experience` KASITLI olarak tam 10 alanla sınırlıdır (D2:
ham cevap/FACT taşıyacak alan yok; tests/test_experience_model.py bunu sabitler). Gerçek
yaşam döngüsü için gereken ek bilgi -- research sinyalleri, güven, provenance, geri bildirim
sayaçları -- buraya, AYRI bir tabloya (reflection_meta) yazılır.

FACT SIZINTISI ENGELİ (yapısal): bu modüldeki HER serbest metin alanı `_reject_fact_like`
süzgecinden geçer -- yüzde, para tutarı ya da takvim yılı içeren bir değer kayda GİRMEZ.
Yani "2026 X oranı %Y" bir deneyim alanına yazılamaz; yazılmaya çalışılırsa hata verilir.
Bu sınır kod seviyesindedir, disiplin değil.
"""
import re
from dataclasses import dataclass, asdict

from learning.experience_model import ExperienceModelError

CONFIDENCE_LOW = "low"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_HIGH = "high"
CONFIDENCES = (CONFIDENCE_LOW, CONFIDENCE_MEDIUM, CONFIDENCE_HIGH)

PROVENANCE_AUTO = "auto:trace"          # KaizenTrace'ten otomatik gözlem
PROVENANCE_USER = "user_feedback"       # kullanıcının onayla:/düzelt: geri bildirimi
PROVENANCES = (PROVENANCE_AUTO, PROVENANCE_USER)

_FACT_LIKE = re.compile(
    r"%|\d\s*(tl|lira|try)\b|\b(tl|lira)\s*\d|(?<![\d.,])(?:19|20)\d{2}(?![\d])|\d+[.,]\d+",
    re.IGNORECASE,
)


def _reject_fact_like(name, value):
    if isinstance(value, (tuple, list)):
        for item in value:
            _reject_fact_like(name, item)
        return
    if isinstance(value, str) and _FACT_LIKE.search(value):
        raise ExperienceModelError(
            f"{name} alani FACT benzeri bir deger tasiyamaz (oran/tutar/yil): {value!r}"
        )


@dataclass(frozen=True)
class ExperienceMeta:
    question_key: str                 # fold_tr(soru)'nun özeti (hash) -- HAM SORU METNİ DEĞİL
    route: str = ""                   # KaizenBrain.last_route
    question_kind: str = ""           # learning.question_profile.KIND_*
    strategy_kind: str = ""           # yeniden kullanılabilir strateji katalog kimliği ('' = gözlem)
    research_used: bool = False
    research_status: str = ""         # yalnız research gerçekten çalıştıysa dolu
    consensus_status: str = ""
    official_source_found: bool = False
    independent_evidence_count: int = 0
    temporal_match: object = None     # True/False/None (None = bilinmiyor/çalışmadı)
    conflict_count: int = 0
    provider_health: str = ""
    confidence: str = CONFIDENCE_LOW
    provenance: str = PROVENANCE_AUTO
    positive_count: int = 0
    negative_count: int = 0

    def __post_init__(self):
        if not self.question_key or not str(self.question_key).strip():
            raise ExperienceModelError("question_key bos olamaz")
        if self.confidence not in CONFIDENCES:
            raise ExperienceModelError(f"bilinmeyen confidence: {self.confidence!r}")
        if self.provenance not in PROVENANCES:
            raise ExperienceModelError(f"bilinmeyen provenance: {self.provenance!r}")
        for name in ("route", "question_kind", "strategy_kind", "research_status",
                     "consensus_status", "provider_health"):
            _reject_fact_like(name, getattr(self, name))
        if self.positive_count < 0 or self.negative_count < 0:
            raise ExperienceModelError("geri bildirim sayaclari negatif olamaz")

    def to_dict(self):
        return asdict(self)
