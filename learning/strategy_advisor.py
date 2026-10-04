"""KAIZEN — StrategyAdvisor: onaylanmış deneyimden SÜREÇ önerisi (asla FACT değil).

Problem A'da öğrenilen çözüm YÖNTEMİ, kelimeleri ve rakamları farklı Problem B'de uygulanabilsin
diye eşleşme SORU YAPISINA göre yapılır (learning/question_profile.py::KIND_*), yüzey
kelimesine göre DEĞİL. Öneri metni learning/strategy_catalog.py'deki sabit süreç tarifidir --
deneyimin kendisi hiçbir metin taşımadığı için (bkz. experience_model D2) öneriden bir oran/
tutar/yıl sızması yapısal olarak imkânsızdır.

ÇALIŞMA KOŞULLARI (hepsi birden):
  1. Yalnız domain=='accounting'. (Çağıran, deterministik katmanlar + FactRegistry + güvenilir
     hafıza SIRASINI zaten geçmiştir; bu sınıf onların YERİNE geçmez.)
  2. Aynı soru türünde, `reusable=True` (yani insan onaylı) en az bir deneyim var.
  3. O deneyimin stratejisi bu soru türüne katalogda UYGUN (negatif transfer reddi: örn.
     "dönem ayrımı" stratejisi bir oran/güncel-FACT sorusuna uygulanmaz).
  4. Net skor >= 1: kayıt başına en çok 1 olumlu (+1) ve 1 olumsuz (-2) sayılır. Olumsuz
     geri bildirim alan deneyimin etkisi düşer/kapanır; tekrarlanan `onayla:` skoru şişirmez.
  5. Onaylanmamış / reusable olmayan deneyim ASLA yönlendirmez (yalnız gözlemdir).
Güven: 'medium' (net>=1) ya da 'high' (net>=3 ve en az 2 farklı soru). Ipucu her durumda
"kesin değil, kaynak yerine geçmez" uyarısıyla verilir.
"""
from dataclasses import dataclass

from learning.question_profile import profile_question
from learning.strategy_catalog import STRATEGIES, strategy_applies_to

ADVICE_NONE = "none"
ADVICE_MEDIUM = "medium"
ADVICE_HIGH = "high"


@dataclass(frozen=True)
class StrategyAdvice:
    strategy_kind: object = None
    guide: str = ""
    confidence: str = ADVICE_NONE
    support: int = 0              # bu stratejiyi onaylayan FARKLI soru sayısı
    net_score: int = 0
    triggers_research: bool = False
    question_kind: str = ""
    rejected_reason: str = ""     # neden öneri VERİLMEDİ (gözlem/trace için)
    source: str = "approved_experience"
    policy_id: object = None
    experience_ids: tuple = ()
    action: str = "prompt_hint"

    @property
    def applied(self):
        return self.confidence != ADVICE_NONE and bool(self.strategy_kind)


class StrategyAdvisor:
    def __init__(self, store):
        self.store = store

    def advise(self, question, domain, needs_current=False):
        if domain != "accounting":
            return StrategyAdvice(rejected_reason="domain_not_supported")
        profile = profile_question(question, domain, needs_current=needs_current)
        rows = self.store.list_by_question_kind(profile.kind)
        if not rows:
            return StrategyAdvice(question_kind=profile.kind, rejected_reason="no_experience_for_structure")

        groups = {}
        for _, experience, meta in rows:
            if not meta.strategy_kind:
                continue
            g = groups.setdefault(meta.strategy_kind, {"net": 0, "support_keys": set(), "reusable": 0, "negative": 0})
            g["net"] += min(meta.positive_count, 1) - 2 * min(meta.negative_count, 1)
            if meta.negative_count:
                g["negative"] += 1
            if experience.reusable and experience.user_approved:
                g["reusable"] += 1
                g["support_keys"].add(meta.question_key)

        best_kind, best = None, None
        rejected = "no_reusable_experience"
        for kind, g in groups.items():
            if g["reusable"] == 0:
                continue
            if not strategy_applies_to(kind, profile.kind):
                rejected = "negative_transfer_structure_mismatch"
                continue
            if g["net"] < 1:
                rejected = "negative_feedback_reduced_influence"
                continue
            if best is None or g["net"] > best["net"]:
                best_kind, best = kind, g
        if best is None:
            return StrategyAdvice(question_kind=profile.kind, rejected_reason=rejected)

        support = len(best["support_keys"])
        confidence = ADVICE_HIGH if (best["net"] >= 3 and support >= 2) else ADVICE_MEDIUM
        spec = STRATEGIES[best_kind]
        return StrategyAdvice(
            strategy_kind=best_kind, guide=spec["guide"], confidence=confidence, support=support,
            net_score=best["net"], triggers_research=spec["triggers_research"],
            question_kind=profile.kind,
        )

    @staticmethod
    def render_hint(advice):
        """Prompt'a eklenecek, FACT içermeyen süreç ipucu."""
        caveat = ("onaylı deneyimden, birden fazla soruda doğrulanmış süreç"
                  if advice.confidence == ADVICE_HIGH else
                  "onaylı deneyimden süreç önerisi, kesin değil")
        return (
            f"\n\n[DENEYİM STRATEJİ İPUCU -- {caveat}]\n{advice.guide}\n"
            "Bu ipucu yalnız bir SÜREÇ önerisidir: kaynak yerine geçmez, hiçbir oran/tutar/yıl/"
            "mevzuat sonucu taşımaz. Yukarıdaki KAYNAK metniyle çelişiyorsa yok say."
        )
