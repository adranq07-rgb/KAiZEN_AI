"""KAIZEN — BÜYÜK GELİŞTİRME PAKETİ #1, Faz D (madde 15, D1-D4): Deneyim/Reflection temeli.

AMAÇ: Kaizen'in bir soruyu NASIL çözdüğünü (hangi ilke, hangi strateji, hangi araçlar/kanıtlar,
sonuç ne oldu, doğrulandı mı) yapılandırılmış bir kayıt olarak TUTAN veri modeli ve depo.
GÜNCEL DURUM (Learning Loop fazı): bu katman artık gerçek cevap yaşam döngüsüne bağlıdır
(`learning/reflection_lifecycle.py` cephesi + `learning/strategy_advisor.py`), ama D2/D3
DEĞİŞMEDİ: bu dataclass hâlâ tam 10 alandır; yeni strateji meta-verisi (research sinyalleri,
güven, provenance, geri bildirim sayaçları) ayrı `learning/experience_meta.py::ExperienceMeta`
kaydında tutulur. `KaizenBrain` bu modülü/depoyu DOĞRUDAN import etmez, yalnız cepheyi kullanır.

KARIŞTIRILMAMASI GEREKEN İKİ AYRI SİSTEM (proje disiplini, principle_seed.py'deki aynı
uyarı deseniyle):
  1. `memory/experience_store.py::ExperienceStore` -- Kaizen'in kendi GÖREV/ARAÇ denetim
     günlüğü (kind: conversation/tool_result/source/correction/skill). Bu, "ne yapıldı"nın
     ham kaydıdır, muhasebe REASONING'i değil.
  2. `memory/brain_manager.py`'nin Cognee tabanlı "deneyim hafızası" (Kademe 2) -- soru/cevap
     çiftlerini EMBEDDING ile anlamsal olarak hatırlar (`remember_experience`/`recall_experience`),
     hiçbir yapılandırılmış alanı (problem_signature/strategy/verification...) yoktur.
  Bu modül ÜÇÜNCÜ, YENİ bir şeydir: bir problemi ÇÖZERKEN hangi ilke/strateji/kanıtın
  kullanıldığının YAPILANDIRILMIŞ izi. Fiziksel depolama ayrı bir dosyadır
  (`data/kaizen_reflections.sqlite3`), yukarıdaki ikisine HİÇ dokunmaz.

D2 (KESİNLİKLE, madde 15, birebir): "Experience is never FACT or VERIFIED LAW." Bu, veri
modeli SEVİYESİNDE yapısal olarak uygulanır -- `Experience` dataclass'ında ham bir "answer_text"
ya da "fact_value" alanı YOKTUR; yalnızca REASONING'in meta-verisi (imza/strateji/araç-kanıt
referanslari/sonuç/doğrulama durumu) tutulur. Bir oran/tutar/tarih/mevzuat hükmü buraya
yazılamaz çünkü onu taşıyacak bir alan hiç yok.

D3 (KESİNLİKLE, madde 15, birebir): "No auto-trust: a new experience never automatically
becomes trusted knowledge." Bu, `ReflectionStore` SEVİYESİNDE zorunlu kılınır:
`user_approved`/`reusable` varsayılan HER ZAMAN False'tur; `reusable=True` yalnızca
`mark_user_approved()` (insanın açık onayı, ayrı bir çağrı) ÖNCEDEN çağrılmışsa
`mark_reusable()` ile mümkündür -- otomatik/toplu/skor-tabanlı bir "artık güvenilir" geçişi
YOKTUR.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"
OUTCOME_REFUSED = "refused"
OUTCOME_UNKNOWN = "unknown"
OUTCOMES = (OUTCOME_SUCCESS, OUTCOME_FAILURE, OUTCOME_REFUSED, OUTCOME_UNKNOWN)

VERIFICATION_NONE = "none"                    # kimse doğrulamadı
VERIFICATION_USER_APPROVED = "user_approved"  # mali müşavir onayladı
VERIFICATION_CROSS_CHECKED = "cross_checked"  # facts/consensus ile çapraz kontrol edildi
VERIFICATIONS = (VERIFICATION_NONE, VERIFICATION_USER_APPROVED, VERIFICATION_CROSS_CHECKED)


class ExperienceModelError(ValueError):
    """Bir Experience alanı D1-D4 kontratını ihlal ettiğinde (madde 15)."""


@dataclass(frozen=True)
class Experience:
    """D1 (madde 15, birebir 10 alan). Ham cevap metni/FACT değeri KASITLI olarak burada
    YOKTUR (D2) -- yalnızca "nasıl çözüldü"nün izi."""

    problem_signature: str        # sorunun yapısal imzası (ör. problem_structure.detect_signals çıktısı)
    selected_principle: object    # kullanılan principle_id (str) ya da None
    strategy: str                 # izlenen yol (ör. "memory_grounded+principle_assist", "research")
    tools_used: tuple             # kullanılan araçların adları (ör. ("retriever", "principle_retriever"))
    evidence_used: tuple          # kanıt referansları (ör. kaynak etiketleri) -- HAM METİN DEĞİL
    outcome: str                  # OUTCOMES'tan biri
    verification: str             # VERIFICATIONS'tan biri
    user_approved: bool = False   # D3: varsayılan False, yalnızca insan onayıyla True olabilir
    reusable: bool = False        # D3: varsayılan False, otomatik True OLAMAZ
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not self.problem_signature or not str(self.problem_signature).strip():
            raise ExperienceModelError("problem_signature bos olamaz")
        if not self.strategy or not str(self.strategy).strip():
            raise ExperienceModelError("strategy bos olamaz")
        if self.outcome not in OUTCOMES:
            raise ExperienceModelError(f"bilinmeyen outcome: {self.outcome!r}")
        if self.verification not in VERIFICATIONS:
            raise ExperienceModelError(f"bilinmeyen verification: {self.verification!r}")
        # D3, yapisal guvence: insan onayi olmadan reusable=True ile OLUSTURULAMAZ (kayit
        # anindaki tek satirlik kisayol bile kapali -- reusable'a giden TEK yol
        # ReflectionStore.mark_user_approved() + mark_reusable() ikilisidir).
        if self.reusable and not self.user_approved:
            raise ExperienceModelError(
                "reusable=True icin once user_approved=True olmali (D3: otomatik guven yok)"
            )
