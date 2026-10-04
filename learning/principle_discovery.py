"""KAIZEN — Brain v2: Autonoum Prinsip Bulma Motoru (İş Emri #21, 22, 24-26).

Bu modül, Kaizen'in "gerçek" öğrenme yeteneğinin merkezidir:
- Çokbağımsız başarılı deneyimlerden strateji ilke çıkarır
- Fact/Strategy güvenlik sınırını kesin şekilde uygular
- İlkeyi DOĞRULA, AKTİF yapar ve KALIcE PERSIST etkin
- Yeni sorularda STRATEJİ GİDENÇ olarak seçilip kullanılır
- Negatif öğrenme (quarantine) destekler
- mevcut ReflectionLifecycle ve StrategyAdvisor ile tam entegrasyon"""

import re
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

from learning.question_profile import (
    KIND_CURRENT_FACT, KIND_PERIOD_PRINCIPLE, KIND_PRINCIPLE,
    KIND_CALCULATION, KIND_JOURNAL, profile_question,
)
from learning.strategy_catalog import STRATEGIES, strategy_applies_to, PERIOD_SEPARATION, RESEARCH_FIRST
from learning.experience_meta import (
    CONFIDENCE_LOW, CONFIDENCE_MEDIUM, CONFIDENCE_HIGH,
    _FACT_LIKE, _reject_fact_like,
)
from learning.experience_model import Experience, OUTCOME_SUCCESS, VERIFICATION_NONE
from learning.reflection_lifecycle import (
    _derive_strategy, _derive_outcome, _derive_confidence,
    NON_LEARNING_ROUTES, question_key,
)
from learning.strategy_advisor import StrategyAdvice, ADVICE_HIGH, ADVICE_MEDIUM, ADVICE_NONE
from memory.principle_registry import PrincipleRegistry, STATUS_ACTIVE, STATUS_DRAFT, STATUS_QUARANTINED
from core.text_tr import fold_tr
from core.trace import KaizenTrace, CONFIDENCE_LEVELS


# ============================================================================
# Constants & Configuration
# ============================================================================

# Mindestens unabhängige destek deneyim sayısı (WORK ORDER #7)
MIN_INDEPENDENT_EXPERIENCES = 3

# İlke yaşam döngüsü aşamaları (WORK ORDER #14)
LIFECYCLE_CANDIDATE = "candidate"
LIFECYCLE_TESTED = "tested"
LIFECYCLE_VALIDATED = "validated"
LIFECYCLE_ACTIVE = "active"
LIFECYCLE_QUARANTINED = "quarantined"

# Fact leakage pattern'ları (WORK ORDER #18)
_FACT_LIKE_PATTERN = re.compile(
    r"%|\d\s*(tl|lira|try)\b|\b(tl|lira)\s*\d|(?<![\d.,])(?:19|20)\d{2}(?![\d])|\d+[.,]\d+",
    re.IGNORECASE,
)


# -------------------------------------------
# İlke tanımı veri yapısı (dataclass)
# -------------------------------------------

@dataclass
class DiscoveredPrinciple:
    """Kaizen'da bağımsız olarak keşfedilen ilke."""
    principle_id: str
    strategy_statement: str  # "dönemi belirle, araştır, doğrula" gibi
    domain: str
    status: str  # candidate, tested, validated, active, quarantined
    supporting_experience_ids: tuple  # hanging experience IDs
    independent_support_count: int  # >=3 olmalı
    success_count: int
    failure_count: int
    confidence: str  # low, medium, high
    created_timestamp: str
    updated_timestamp: str
    last_used_timestamp: str
    validation_history: list  # [(reason, outcome, timestamp)]
    quarantine_reason: str = None  # why was it quarantined?
    origin: str = "autonomous"  # manual / existing / autonomous_discovery

    def to_dict(self):
        return {
            "principle_id": self.principle_id,
            "strategy_statement": self.strategy_statement,
            "domain": self.domain,
            "status": self.status,
            "supporting_experience_ids": list(self.supporting_experience_ids),
            "independent_support_count": self.independent_support_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "confidence": self.confidence,
            "created_timestamp": self.created_timestamp,
            "updated_timestamp": self.updated_timestamp,
            "last_used_timestamp": self.last_used_timestamp,
            "validation_history": self.validation_history,
            "quarantine_reason": self.quarantine_reason,
            "origin": self.origin,
        }

    @staticmethod
    def from_dict(d):
        return DiscoveredPrinciple(
            principle_id=d["principle_id"],
            strategy_statement=d["strategy_statement"],
            domain=d["domain"],
            status=d["status"],
            supporting_experience_ids=tuple(d.get("supporting_experience_ids", [])),
            independent_support_count=d.get("independent_support_count", 0),
            success_count=d.get("success_count", 0),
            failure_count=d.get("failure_count", 0),
            confidence=d.get("confidence", CONFIDENCE_LOW),
            created_timestamp=d.get("created_timestamp", datetime.now(timezone.utc).isoformat()),
            updated_timestamp=d.get("updated_timestamp", datetime.now(timezone.utc).isoformat()),
            last_used_timestamp=d.get("last_used_timestamp", datetime.now(timezone.utc).isoformat()),
            validation_history=d.get("validation_history", []),
            quarantine_reason=d.get("quarantine_reason"),
            origin=d.get("origin", "autonomous"),
        )


# -------------------------------------------
# Ana Prinsip Bulma Motoru
# -------------------------------------------

class PrincipleDiscoveryEngine:
    """Kaizen'ın AKTİF prensip keşif pipelinini çalıştıran motor."""

    def __init__(self, principle_registry: PrincipleRegistry,
                 store, brain_manager,
                 min_independent: int = MIN_INDEPENDENT_EXPERIENCES,
                 ):
        self.registry = principle_registry
        self.reflection_store = store
        self.brain_manager = brain_manager
        self.min_independent = min_independent
        self.max_experiences_to_review = 200

    # -------------------------------------------
    # Phase 1: Eligibility Filtering
    # -------------------------------------------

    def _collect_successful_experiences(self) -> list:
        """Başarılı (success) deneyimleri toplayar.
        Sadece accounting domain ve reusable=True deneyimler."""

        # ReflectionStore.list_with_meta() returns (rid, Experience, ExperienceMeta) tuples
        all_reflections = self.reflection_store.list_with_meta(None)

        successful = []
        for rid, exp, meta in all_reflections:
            if exp.outcome != OUTCOME_SUCCESS:
                continue
            if not exp.reusable:
                continue
            successful.append((rid, exp, meta))

        return successful

    # -------------------------------------------
    # Phase 2: Grouping Related Experiences
    # -------------------------------------------

    def _group_by_question_kind(self, experiences: list) -> dict:
        """Benzer yapısal imzaya sahip deneyimleri gruplar.
        question_kind (KIND_CURRENT_FACT, KIND_PERIOD_PRINCIPLE, vb.) göre."""

        groups = defaultdict(list)
        for rid, exp, meta in experiences:
            qk = meta.question_kind if meta else ""
            groups[qk].append((rid, exp, meta))

        return dict(groups)

    # -------------------------------------------
    # Phase 3: Recurring Strategy Detection
    # -------------------------------------------

    def _detect_recurring_strategy(self, group_experiences: list) -> str | None:
        """Bir gruptaki deneyimlerde tekrar eden stratejiyi tespit eder."""

        if not group_experiences:
            return None

        strategy_counts = defaultdict(int)
        for rid, exp, meta in group_experiences:
            strategy_kind = meta.strategy_kind if meta else ""
            if strategy_kind:
                strategy_counts[strategy_kind] += 1

        if not strategy_counts:
            return None

        best_strategy = max(strategy_counts, key=strategy_counts.get)

        if strategy_counts[best_strategy] < 2:
            return None

        return best_strategy

    # -------------------------------------------
    # Phase 4: Candidate Principle Creation
    # -------------------------------------------

    def _create_candidate_principle(self, strategy_kind: str,
                                    supporting_exps: list,
                                    domain: str = "accounting") -> dict | None:
        """Strateji Kind'ten ilke candidate'ı oluşturur.
        Strategy catalog'tan rehber alınır."""

        spec = STRATEGIES.get(strategy_kind)
        if spec is None:
            strategy_statement = f"Sorunun {strategy_kind} türüne uygun çözümlenmesi"
        else:
            strategy_statement = spec["guide"]

        # Fact leakage guard: stratejide year/specific values yok
        if _principle_has_fact_leak(strategy_statement,
                                     strategy_statement):
            return None

        principle_id = f"autonomous_{strategy_kind}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        candidate = {
            "principle_id": principle_id,
            "name": f"Otonom keşif: {strategy_kind}",
            "description": strategy_statement,
            "domain": domain,
            "problem_structure": supporting_exps[0].problem_signature if supporting_exps else "",
            "applicability": self._derive_applicability(supporting_exps),
            "non_applicability": self._derive_non_applicability(supporting_exps),
            "examples": self._derive_examples(supporting_exps),
            "counter_examples": [],
            "source": "autonomous_discovery",
            "status": LIFECYCLE_CANDIDATE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "independent_support_count": len(set(
                exp for _, exp, _ in supporting_exps
            )),
            "success_count": sum(1 for _, exp, _ in supporting_exps if exp.outcome == OUTCOME_SUCCESS),
            "failure_count": sum(1 for _, exp, _ in supporting_exps if exp.outcome == "failure"),
            "confidence": self._compute_confidence(len(supporting_exps)),
            "supporting_experience_ids": tuple(rid for rid, _, _ in supporting_exps),
            "validation_history": [],
        }

        return candidate

    def _derive_applicability(self, exps: list) -> str:
        """Stratejinin uygulanabileceği senaryoları tanımlar."""
        kinds = set()
        for _, exp, meta in exps:
            qk = meta.question_kind if meta else ""
            kinds.add(qk)
        return json.dumps(sorted(kinds))

    def _derive_non_applicability(self, exps: list) -> str:
        """Stratejinin UYGULANMAZ hali (negatif transfer)."""
        non_applicable = set()
        for _, exp, meta in exps:
            if meta and meta.strategy_kind:
                if meta.strategy_kind == "current_fact":
                    non_applicable.add("current_fact_to_period_principle")
        return json.dumps(sorted(non_applicable))

    def _derive_examples(self, exps: list) -> list:
        """Stratejinin çalıştığı örnek senaryoları (FACT DEĞİL, sadece süreç imzası)."""
        examples = []
        for _, exp, meta in exps[:3]:
            sig = exp.problem_signature
            examples.append(sig[:80] if sig else "bilinmeyen senaryo")
        return examples

    # -------------------------------------------
    # Phase 5: Fact/Strategy Safety Guard
    # -------------------------------------------

    def _fact_safety_guard(self, candidate: dict) -> bool:
        """Candidate ilkeye FACT sızıntısı guard'u uygular."""
        name = candidate.get("name", "")
        description = candidate.get("description", "")

        if _principle_has_fact_leak(name, description):
            return False

        ps = candidate.get("problem_structure", "")
        if _FACT_LIKE_PATTERN.search(str(ps)):
            return False

        return True

    # -------------------------------------------
    # Phase 6: Confidence Computation
    # -------------------------------------------

    def _compute_confidence(self, independent_count: int) -> str:
        """Bağımsız destek sayısına göre güveni hesaplar."""
        if independent_count >= 3:
            return CONFIDENCE_HIGH
        elif independent_count >= 2:
            return CONFIDENCE_MEDIUM
        elif independent_count >= 1:
            return CONFIDENCE_LOW
        else:
            return CONFIDENCE_LOW

    # -------------------------------------------
    # Phase 7: Validation
    # -------------------------------------------

    def _validate_candidate(self, candidate: dict) -> dict:
        """Candidate ilkeyi destek evidence ile doğrular."""

        validation_result = {
            "validated": False,
            "reasons": [],
            "evidence_used": [],
        }

        supporting_ids = candidate.get("supporting_experience_ids", [])
        if len(supporting_ids) < self.min_independent:
            validation_result["reasons"].append(
                f"Yetersiz bağımsız destek: {len(supporting_ids)} < {self.min_independent}"
            )
            return validation_result

        all_supported = True
        validated_count = 0
        for rid in supporting_ids:
            exp = self.reflection_store.get(rid)
            if exp is None:
                continue
            if exp.outcome == OUTCOME_SUCCESS:
                validated_count += 1
            else:
                all_supported = False
                validation_result["reasons"].append(
                    f"Deneyim {rid}: outcome={exp.outcome}, beklenen success"
                )

        if validated_count >= self.min_independent and all_supported:
            validation_result["validated"] = True
            validation_result["reasons"].append(
                f"{validated_count} bağımsız deneyim başarıyla doğrulandı"
            )
        else:
            validation_result["reasons"].append(
                f"Yeterli bağımsız başarı yok: {validated_count}/{len(supporting_ids)} success"
            )

        return validation_result

    # -------------------------------------------
    # Phase 8: Persistence & Lifecycle Management
    # -------------------------------------------

    def _persist_principle(self, candidate: dict, validation: dict) -> str | None:
        """Geçici candidate'ı PrincipleRegistry'a kaydeder/aktifleştirir."""

        if not validation.get("validated"):
            candidate["status"] = LIFECYCLE_TESTED
            candidate["quarantine_reason"] = "; ".join(validation.get("reasons", []))
            self.registry.upsert(
                principle_id=candidate["principle_id"],
                name=candidate["name"],
                description=candidate["description"],
                domain=candidate["domain"],
                problem_structure=candidate.get("problem_structure", ""),
                applicability=candidate.get("applicability", ""),
                non_applicability=candidate.get("non_applicability", ""),
                examples=candidate.get("examples", []),
                counter_examples=candidate.get("counter_examples", []),
                source=candidate.get("source", "autonomous_discovery"),
                status=LIFECYCLE_TESTED,
            )
            return None

        # Validate oldu -- ACTIVE yap
        candidate["status"] = LIFECYCLE_ACTIVE
        candidate["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.registry.upsert(
            principle_id=candidate["principle_id"],
            name=candidate["name"],
            description=candidate["description"],
            domain=candidate["domain"],
            problem_structure=candidate.get("problem_structure", ""),
            applicability=candidate.get("applicability", ""),
            non_applicability=candidate.get("non_applicability", ""),
            examples=candidate.get("examples", []),
            counter_examples=candidate.get("counter_examples", []),
            source=candidate.get("source", "autonomous_discovery"),
            status=LIFECYCLE_ACTIVE,
        )

        # Already exists with same ID? reuse
        existing = self.registry.get(candidate["principle_id"])
        if existing and existing.get("status") == LIFECYCLE_ACTIVE:
            old_support = existing.get("independent_support_count", 0)
            new_support = candidate["independent_support_count"]
            candidate["confidence"] = self._compute_confidence(new_support)

        return candidate["principle_id"]

    # -------------------------------------------
    # Main Discovery Pipeline
    # -------------------------------------------

    def discover_principle(self) -> dict | None:
        """Tam keşif pipelinisini çalıştırır.
        RETURN: Başarıyla aktifleştirilen ilke dict'i ya da None."""

        experiences = self._collect_successful_experiences()

        if len(experiences) < self.min_independent:
            return None

        groups = self._group_by_question_kind(experiences)

        for question_kind, group_exps in groups.items():
            if len(group_exps) < self.min_independent:
                continue

            strategy_kind = self._detect_recurring_strategy(group_exps)
            if strategy_kind is None:
                continue

            candidate = self._create_candidate_principle(
                strategy_kind, group_exps, "accounting"
            )
            if candidate is None:
                continue

            # DEDUP: Eşdeğer bir ilke zaten ACTIVE ise yeni candidate oluşturma
            existing_id = self._equivalent_principle_exists(candidate)
            if existing_id is not None:
                continue

            if not self._fact_safety_guard(candidate):
                continue

            validation = self._validate_candidate(candidate)
            if not validation.get("validated"):
                self._persist_principle(candidate, validation)
                continue

            principle_id = self._persist_principle(candidate, validation)
            if principle_id is None:
                continue

            principle = self.registry.get(principle_id)
            if principle:
                return principle

        return None

    # -------------------------------------------
    # Principle Retrieval for Runtime
    # -------------------------------------------

    def retrieve_principle_for_question(self, question: str) -> dict | None:
        """Yeni bir soru için uygulanabilecek AKTİF ilkeyiRetrieve eder."""

        profile = profile_question(question, "accounting", needs_current=False)

        all_principles = self.registry.all(domain="accounting", status=LIFECYCLE_ACTIVE)

        best = None
        best_score = -1

        for p in all_principles:
            ps = p.get("problem_structure", "")
            from learning.problem_structure import detect_signals
            signals = detect_signals(question)

            score = 0
            if strategy_applies_to(p.get("name", ""), profile.kind):
                score += 3

            if "RATE_QUERY" in signals:
                continue

            name_lower = p.get("name", "").lower()
            folded = fold_tr(question)
            for kw in p.get("applicability", "").split(","):
                kw = kw.strip()
                if kw and kw in folded:
                    score += 1

            if score > best_score:
                best_score = score
                best = p

        if best and best_score >= 1:
            return best

        return None

    # -------------------------------------------
    # Negative Learning / Quarantine
    # -------------------------------------------

    def record_outcome(self, principle_id: str, outcome_success: bool):
        """Ilke sonucunu kaydedip güveni/confidence'yi günceller."""

        principle = self.registry.get(principle_id)
        if principle is None:
            return

        if outcome_success:
            principle["success_count"] = principle.get("success_count", 0) + 1
        else:
            principle["failure_count"] = principle.get("failure_count", 0) + 1

        total = principle.get("success_count", 0) + principle.get("failure_count", 0)

        if not outcome_success and principle.get("failure_count", 0) >= 3:
            principle["status"] = LIFECYCLE_QUARANTINED
            principle["quarantine_reason"] = (
                f"{principle['failure_count']} başarısızlık sonucu confidence azalttı"
            )
        elif outcome_success:
            principle["confidence"] = CONFIDENCE_HIGH
        else:
            if total > 0:
                failure_ratio = principle["failure_count"] / total
                if failure_ratio > 0.5 and principle["confidence"] != CONFIDENCE_LOW:
                    principle["confidence"] = CONFIDENCE_LOW

        principle["updated_at"] = datetime.now(timezone.utc).isoformat()
        principle["last_used_timestamp"] = datetime.now(timezone.utc).isoformat()

        self.registry.upsert(
            principle_id=principle_id,
            name=principle["name"],
            description=principle["description"],
            domain=principle["domain"],
            problem_structure=principle.get("problem_structure", ""),
            applicability=principle.get("applicability", ""),
            non_applicability=principle.get("non_applicability", ""),
            examples=principle.get("examples", []),
            counter_examples=principle.get("counter_examples", []),
            source=principle.get("source", "autonomous_discovery"),
            status=principle["status"],
            independent_support_count=principle.get("independent_support_count", 0),
            success_count=principle.get("success_count", 0),
            failure_count=principle.get("failure_count", 0),
            confidence=principle.get("confidence", "low"),
            supporting_experience_ids=principle.get("supporting_experience_ids", ()),
            validation_history=principle.get("validation_history", []),
            quarantine_reason=principle.get("quarantine_reason"),
        )
        # Re-fetch to return the persisted state
        return self.registry.get(principle_id)

    # -------------------------------------------
    # Deduplication: check if equivalent principle already exists
    # -------------------------------------------

    def _equivalent_principle_exists(self, new_candidate: dict) -> str | None:
        """Benzer bir ilke zaten varsa its principle_id'yi döndürür."""

        all_principles = self.registry.all(domain="accounting", status=LIFECYCLE_ACTIVE)

        new_ps = new_candidate.get("problem_structure", "")
        new_name = new_candidate.get("name", "")

        for p in all_principles:
            existing_ps = p.get("problem_structure", "")
            if new_ps and existing_ps:
                try:
                    new_sig = json.loads(new_ps) if isinstance(new_ps, str) else new_ps
                    existing_sig = json.loads(existing_ps) if isinstance(existing_ps, str) else existing_ps
                    if new_sig == existing_sig:
                        return p["principle_id"]
                except (json.JSONDecodeError, TypeError):
                    pass
            if new_name.lower() in p.get("name", "").lower():
                return p["principle_id"]

        return None


# Note: _FACT_SAFETY_SIGNAL learning/principle_retriever.py'deki gibi kullanılmayacak;
# bu modül kendi guard'ını (_fact_safety_guard) kullanır.