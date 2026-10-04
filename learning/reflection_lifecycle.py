"""KAIZEN — Reflection/Experience YAŞAM DÖNGÜSÜ cephesi.

`KaizenBrain` ReflectionStore'a/Experience modeline DOĞRUDAN dokunmaz; yalnız bu cepheyi
çağırır (D2/D3 kontratı tek yerde korunur):

  record_answer(...)  -- bir cevap verildikten SONRA, o cevabın nasıl üretildiğinin
                         YAPISAL izini (problem imzası, strateji, route, research metadata,
                         sonuç, güven, provenance) kaydeder. Ham cevap/FACT ASLA yazılmaz.
  apply_feedback(...) -- `onayla:` (olumlu) / `düzelt:` (olumsuz) sonucunu ilgili TEK
                         deneyime bağlar.

DEĞİŞMEZLER (test edilir):
  * Reflection otomatik olarak VERIFIED FACT üretmez: bu modül FactRegistry'ye/kartlara HİÇ
    yazmaz, yalnız ReflectionStore'a yazar.
  * Yeni kayıt HER ZAMAN reusable=False, user_approved=False başlar (D3). `reusable` yalnız
    insan onayı (onayla:) + katalogda karşılığı olan bir strateji + sıfır olumsuz geri
    bildirim ile açılır.
  * Deterministik/kesin araç ve FactRegistry rotaları (arithmetic/calculator/chart/journal/
    facts) ve kullanıcı düzeltmesi bir "çözüm stratejisi" DEĞİLDİR: kayıt edilmez -- bu
    katmanlar deneyimden ETKİLENMEZ ve deneyim onları etkilemez.
  * Olumsuz geri bildirim YAPIŞKANDIR ve yalnız İLGİLİ TEK kaydı etkiler; yanlış bir
    `onayla:` tek başına sistemi zehirleyemez (bkz. StrategyAdvisor: kayıt başına en çok 1
    olumlu / 1 olumsuz sayılır, olumsuz 2x ağırlıklıdır).
"""
import hashlib

from core.text_tr import fold_tr
from learning.experience_meta import (
    CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM, PROVENANCE_AUTO,
    ExperienceMeta, _reject_fact_like,
)
from learning.experience_model import (
    Experience, OUTCOME_REFUSED, OUTCOME_SUCCESS, OUTCOME_UNKNOWN,
    VERIFICATION_CROSS_CHECKED, VERIFICATION_NONE,
)
from learning.question_profile import (
    KIND_CALCULATION, KIND_CURRENT_FACT, KIND_JOURNAL, KIND_PERIOD_PRINCIPLE,
    KIND_PRINCIPLE, profile_question,
)
from learning.strategy_catalog import (
    ASK_MISSING, PERIOD_SEPARATION, PRINCIPLE_GROUNDED, RESEARCH_FIRST, strategy_applies_to,
)

# Bir "çözüm stratejisi" değil, deterministik/otoriter katman rotaları: KAYIT EDİLMEZ.
NON_LEARNING_ROUTES = frozenset({"empty", "correction", "arithmetic", "calculator", "chart", "facts"})
REFUSAL_ROUTES = frozenset({"not_found_offline", "office_missing"})
GROUNDED_SUCCESS_ROUTES = frozenset({"memory_grounded", "memory_extractive", "memory_card_confirmed"})
_MISSING_PARAM_MARKER = "belirtmediniz"


def question_key(question):
    """Sorunun özet anahtarı (ham metin DEĞİL): geri bildirimi doğru deneyime bağlar."""
    folded = fold_tr(question.strip())
    for prefix in ("muhasebe:", "matematik:"):
        if folded.startswith(prefix):
            folded = folded[len(prefix):].strip()
            break
    return hashlib.sha256(folded.encode("utf-8")).hexdigest()[:24]


def _clean_labels(values):
    """Kanıt etiketleri: yalnız alan adı benzeri, FACT benzeri (yüzde/tutar/yıl) OLMAYANLAR."""
    cleaned = []
    for value in values or ():
        try:
            _reject_fact_like("evidence_used", value)
        except Exception:
            continue
        cleaned.append(str(value))
    return tuple(cleaned)


def _derive_strategy(profile, route, research_meta, answer_text, used_research):
    if route in REFUSAL_ROUTES:
        return ""
    if profile.kind == KIND_CURRENT_FACT and used_research and route == "research":
        return RESEARCH_FIRST
    if route == "journal" and answer_text and _MISSING_PARAM_MARKER in fold_tr(answer_text):
        return ASK_MISSING
    if route in GROUNDED_SUCCESS_ROUTES:
        if profile.kind == KIND_PERIOD_PRINCIPLE:
            return PERIOD_SEPARATION
        if profile.kind == KIND_PRINCIPLE:
            return PRINCIPLE_GROUNDED
    return ""


def _derive_outcome(route, research_meta):
    if route in REFUSAL_ROUTES:
        return OUTCOME_REFUSED
    if route in GROUNDED_SUCCESS_ROUTES:
        return OUTCOME_SUCCESS
    if route == "research" and research_meta and research_meta.get("status") == "SUPPORTED":
        return OUTCOME_SUCCESS
    return OUTCOME_UNKNOWN


def _derive_confidence(outcome, route, research_meta):
    if research_meta and research_meta.get("status") == "SUPPORTED":
        official = research_meta.get("official_evidence_count", 0) > 0
        independent = research_meta.get("independent_source_count", 0) >= 2
        return CONFIDENCE_HIGH if (official or independent) else CONFIDENCE_MEDIUM
    if route in GROUNDED_SUCCESS_ROUTES:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


class ReflectionLifecycle:
    def __init__(self, store):
        self.store = store

    # ------------------------------------------------------------------ kayıt
    def record_answer(self, question, domain, trace, answer_text=None, research_meta=None,
                      needs_current=False, reasoning_context=None):
        """Bir cevaptan SONRA yapısal deneyimi kaydeder; `{record_id, strategy_kind,
        reusable_candidate}` döner ya da kayıt edilmemesi gerekiyorsa None.

        reasoning_context (AccountingReasoningContext): Accountant Reasoning Core v1'den
        gelen internal structured decision state. Bu yalnızca trace ve future learning
        için saklanır, ham cevap/FACT taşımaz."""
        route = trace.route
        journal_missing = (route == "journal" and answer_text
                           and _MISSING_PARAM_MARKER in fold_tr(answer_text))
        if not route or (route in NON_LEARNING_ROUTES) or (route == "journal" and not journal_missing):
            return None
        profile = profile_question(question, domain, needs_current=needs_current)
        strategy_kind = _derive_strategy(profile, route, research_meta, answer_text,
                                         used_research=bool(trace.used_research))
        outcome = _derive_outcome(route, research_meta)
        confidence = _derive_confidence(outcome, route, research_meta)
        engine_supported = bool(research_meta and research_meta.get("status") == "SUPPORTED")

        tools = []
        if trace.used_facts:
            tools.append("facts")
        if trace.used_memory:
            tools.append("retriever")
        if trace.used_research:
            tools.append("research_engine" if research_meta else "hermes_research")
        if trace.used_model:
            tools.append("model")
        if trace.principle_selected:
            tools.append("principle_retriever")

        experience = Experience(
            problem_signature=profile.signature,
            selected_principle=trace.principle_selected,
            strategy=strategy_kind or f"route:{route}",
            tools_used=tuple(tools),
            evidence_used=_clean_labels((research_meta or {}).get("source_domains")),
            outcome=outcome,
            verification=VERIFICATION_CROSS_CHECKED if engine_supported else VERIFICATION_NONE,
        )
        meta = ExperienceMeta(
            question_key=question_key(question),
            route=route,
            question_kind=profile.kind,
            strategy_kind=strategy_kind,
            research_used=bool(trace.used_research),
            research_status=(research_meta or {}).get("status", ""),
            consensus_status=(research_meta or {}).get("consensus_status", ""),
            official_source_found=bool(research_meta and research_meta.get("official_evidence_count", 0) > 0),
            independent_evidence_count=int((research_meta or {}).get("independent_source_count", 0)),
            temporal_match=(research_meta or {}).get("temporal_match"),
            conflict_count=int((research_meta or {}).get("conflict_count", 0)),
            provider_health=(research_meta or {}).get("search_health", "") or "",
            confidence=confidence,
            provenance=PROVENANCE_AUTO,
        )
        record_id = self.store.record(experience, meta, reasoning_context=reasoning_context)
        return {"record_id": record_id, "strategy_kind": strategy_kind,
                "reusable_candidate": bool(strategy_kind), "outcome": outcome,
                "confidence": confidence}

    # ------------------------------------------------------------ geri bildirim
    def apply_feedback(self, question, positive):
        """`onayla:` (positive=True) / `düzelt:` (positive=False). En son ilgili TEK
        deneyime uygulanır. Bu deneyim yoksa uydurma bir kayıt OLUŞTURULMAZ."""
        rid = self.store.find_latest_by_question_key(question_key(question))
        if rid is None:
            return {"applied": False, "reason": "no_experience_for_question"}
        meta = self.store.get_meta(rid)
        experience = self.store.get(rid)
        allow_reusable = bool(
            positive and meta.strategy_kind
            and strategy_applies_to(meta.strategy_kind, meta.question_kind)
            and experience.outcome != OUTCOME_REFUSED
        )
        effect = self.store.apply_feedback(rid, positive, allow_reusable=allow_reusable)
        effect.update(applied=True, record_id=rid, strategy_kind=meta.strategy_kind,
                      feedback="positive" if positive else "negative")
        return effect
