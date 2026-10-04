"""KAIZEN Learning Brain v1 — RUN1 vs RUN2 Strategy Transfer Acceptance Test.

Kanıtlayacağımız:
  1. RUN1: Yeni bir problem ile Kaizen normal pipeline ile çözer
  2. onayla: ile destekler
  3. RUN2: Aynı çözüm STRATEJİSİNİ gerektiren farklı ifadeli problemde
     Kaizen geçmiş deneyimden retrieve eder, applicability kontrolü yapar,
     öğrenilmiş stratejiyi kullanır
  4. Karşılaştırma: strategy reuse, tool calls, model calls, research calls,
     latency, correctness, fact safety

ÇÖZÜM: İki brain aynı ReflectionStore'u paylaşır (farklı BrainManager/ LearningStore
kullanırlar ama ReflectionStore tek). Böylece RUN2'nin StrategyAdvisor'ı RUN1'in
onaylı deneyimini görebilir.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

from core.commands import CommandHandler
from core.kaizen_brain import KaizenBrain
from learning.reflection_lifecycle import ReflectionLifecycle, question_key
from learning.reflection_store import ReflectionStore
from learning.strategy_advisor import StrategyAdvisor
from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds
from research.fetcher import FetchOutcome
from tests.doubles import NullExperienceMemory
from tests.test_kaizen_brain_research_engine import (
    _FakeFetcher, _FakeSearchProvider, _html, _sr,
)
from tests.test_learning_loop import (
    _RecordingProvider, _CorrectingAgent,
)

RESEARCH_Q = "2026 SGK prim tavanı nedir?"
RESEARCH_Q_B = "Bu yıl SGK prime esas kazanç üst sınırı ne kadar?"  # Same STRATEGY, different wording


def _fetch(url, sentence="2026 yılı için SGK prim tavanı 750.000 TL'dir.", year="2026"):
    body = _html(sentence).replace(b"2026-01-05", f"{year}-01-05".encode())
    return FetchOutcome(
        status="FETCH_OK", url=url, final_url=url,
        content_type="text/html; charset=utf-8", body=body,
    )


def _setup(pages, q=RESEARCH_Q):
    prov = _FakeSearchProvider(results=[_sr(u, q) for u in pages])
    return prov, _FakeFetcher({u: _fetch(u, s, y) for u, (s, y) in pages.items()})


def _make_brain(tmp: str, reflections: ReflectionStore, provider=None, fetcher=None):
    """Aynı ReflectionStore'u paylaşan bir brain oluşturur (RUN1/RUN2 paylaşımlı)."""
    store = LearningStore(Path(tmp) / "learning.sqlite3")
    load_seeds(store)
    brain = KaizenBrain(
        _RecordingProvider(), _CorrectingAgent(),
        brain_manager=BrainManager(
            learning_store=store, experience_memory=NullExperienceMemory(),
            log_dir=tmp,
        ),
        research_engine_enabled=True, search_provider=provider,
        research_fetcher=fetcher,
        reflection_lifecycle=ReflectionLifecycle(reflections),
        strategy_advisor=StrategyAdvisor(reflections),
    )
    return brain


def _report_run(label, brain, elapsed):
    t = brain.last_trace
    print(f"\n--- {label} ---")
    print(f"Route   : {t.route}")
    print(f"Outcome : {t.outcome}")
    print(f"Confidence: {t.confidence}")
    print(f"Model calls  : {t.model_calls}")
    print(f"Research used: {t.used_research}")
    print(f"Research status: {t.research_status}")
    print(f"Experience candidate: {t.experience_candidate}")
    print(f"Experience reusable: {t.experience_reusable}")
    print(f"Experience advice  : {t.experience_advice}")
    print(f"Latency (ms) : {elapsed:.1f}")
    return t


def main():
    with tempfile.TemporaryDirectory() as tmp:
        # Tek ReflectionStore — iki run arasında paylaşılır
        shared_reflections = ReflectionStore(Path(tmp) / "shared_reflections.sqlite3")

        # ================================================================
        # RUN 1: İlk problem — strateji öğrenilir
        # ================================================================
        print("=" * 70)
        print("RUN 1 — İlk problem çözümü ve onay")
        print("=" * 70)

        pages = {"https://www.sgk.gov.tr/duyuru/2026": (
            "2026 yılı için SGK prim tavanı 750.000 TL'dir.", "2026"
        )}
        p, f = _setup(pages)
        brain1 = _make_brain(tmp + "/run1", shared_reflections, provider=p, fetcher=f)

        t0 = time.perf_counter()
        answer1 = brain1.answer(RESEARCH_Q)
        elapsed1 = (time.perf_counter() - t0) * 1000
        t1 = _report_run("RUN 1 — İlk problem", brain1, elapsed1)

        # onayla:
        class _Engine: pass
        engine = _Engine()
        engine.brain = brain1
        engine.cards = object()
        engine.accounting_agent = brain1.accounting_agent
        handler = CommandHandler(engine)
        feedback_reply = handler.handle(f"onayla: {RESEARCH_Q}")
        print(f"Feedback reply: {feedback_reply[:80]}")

        # Check experience recorded
        rid1 = shared_reflections.find_latest_by_question_key(question_key(RESEARCH_Q))
        assert rid1 is not None, "RUN1: experience not recorded"
        exp1 = shared_reflections.get(rid1)
        assert exp1.user_approved is True, "RUN1: user_approved not set"
        assert exp1.reusable is True, "RUN1: reusable not set"
        print(f"RUN1 Experience: user_approved={exp1.user_approved}, reusable={exp1.reusable}")

        run1_result = {
            "question": RESEARCH_Q,
            "route": t1.route,
            "outcome": t1.outcome,
            "confidence": t1.confidence,
            "model_calls": t1.model_calls,
            "used_research": t1.used_research,
            "research_status": t1.research_status,
            "latency_ms": round(elapsed1, 1),
            "experience_candidate": t1.experience_candidate,
            "experience_reusable": t1.experience_reusable,
        }

        # ================================================================
        # RUN 2: Farklı ifade, aynı strateji — transfer beklenir
        # ================================================================
        print()
        print("=" * 70)
        print("RUN 2 — Farklı ifade, AYNI strateji — transfer beklenir")
        print("=" * 70)

        pages2 = {"https://www.sgk.gov.tr/duyuru/2027": (
            "2026 yılı için SGK prim tavanı 750.000 TL'dir.", "2026"
        )}
        p2, f2 = _setup(pages2, q=RESEARCH_Q_B)
        brain2 = _make_brain(tmp + "/run2", shared_reflections, provider=p2, fetcher=f2)

        t0 = time.perf_counter()
        answer2 = brain2.answer(RESEARCH_Q_B)
        elapsed2 = (time.perf_counter() - t0) * 1000
        t2 = _report_run("RUN 2 — Farklı ifade, aynı strateji", brain2, elapsed2)

        run2_result = {
            "question": RESEARCH_Q_B,
            "route": t2.route,
            "outcome": t2.outcome,
            "confidence": t2.confidence,
            "model_calls": t2.model_calls,
            "used_research": t2.used_research,
            "research_status": t2.research_status,
            "latency_ms": round(elapsed2, 1),
            "experience_candidate": t2.experience_candidate,
            "experience_reusable": t2.experience_reusable,
        }

        # ================================================================
        # KARŞILAŞTIRMA
        # ================================================================
        print()
        print("=" * 70)
        print("RUN1 vs RUN2 KARŞILAŞTIRMA")
        print("=" * 70)

        fact_safety_ok = t1.confidence != "VERIFIED" and t2.confidence != "VERIFIED"
        transfer_detected = (
            t2.experience_reusable is True
            or t2.experience_advice is not None
        )

        print(f"RUN1 confidence : {t1.confidence}")
        print(f"RUN2 confidence : {t2.confidence}")
        print(f"RUN1 outcome    : {t1.outcome}")
        print(f"RUN2 outcome    : {t2.outcome}")
        print(f"RUN2 experience_reusable: {t2.experience_reusable}")
        print(f"RUN2 experience_advice  : {t2.experience_advice}")
        print(f"Fact safety OK  : {fact_safety_ok}")
        print(f"Transfer detected: {transfer_detected}")

        comparison = {
            "run1": run1_result,
            "run2": run2_result,
            "fact_safety_ok": fact_safety_ok,
            "transfer_detected": transfer_detected,
            "latency_diff_ms": round(elapsed2 - elapsed1, 1),
        }
        print()
        print(json.dumps(comparison, indent=2, ensure_ascii=False))

        success = True
        if not fact_safety_ok:
            print("FAIL: FACT safety violated")
            success = False
        if not transfer_detected:
            print("FAIL: Strategy transfer not detected in RUN2")
            success = False

        if success:
            print("\nRUN1 vs RUN2 STRATEGY TRANSFER: PASS")
        else:
            print("\nRUN1 vs RUN2 STRATEGY TRANSFER: FAIL")

        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())