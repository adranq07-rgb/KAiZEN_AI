"""Accountant Reasoning Core v1 — Targeted regression tests.

Bu testler yalnızca Accountant Reasoning Core'un yeni davranışını korur:
- Mizan nedir? → foundation knowledge, research FALSE
- Vadeli mal aldım → transaction problem type, concepts
- 2026 SGK prim tavanı → current_fact_needed TRUE, truth boundary
"""
import tempfile
from pathlib import Path

from config.config_manager import ConfigManager
from core.ai.offline_provider import OfflineProvider
from core.engine import KaizenEngine
from tests.doubles import NullExperienceMemory


def _make_config():
    config = ConfigManager()
    config.config["learning"].update(
        learning_brain_enabled=True,
        experience_lifecycle_enabled=True,
        experience_advice_enabled=True,
        runtime_learning_enabled=True,
        principle_discovery_enabled=False,
    )
    config.config["retrieval"] = {"hybrid_enabled": False}
    config.config["research"] = {"research_engine_enabled": False}
    return config


def _make_engine(tmp):
    return KaizenEngine(
        data_dir=Path(tmp) / "data",
        log_dir=Path(tmp) / "logs",
        provider=OfflineProvider(),
        config=_make_config(),
        experience_memory=NullExperienceMemory(),
    )


def test_mizan_reasoning_context():
    """Mizan nedir? → foundation knowledge, research FALSE."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = _make_engine(tmp)
        try:
            engine.cevap_ver("Mizan nedir?")
            trace = engine.brain.last_trace
            assert trace.accounting_reasoning_used, "Reasoning context kullanılmalı"
            assert trace.problem_type == "definition", f"definition olmalı, got {trace.problem_type}"
            assert trace.current_fact_needed is False, "current_fact_needed FALSE olmalı"
            assert "research_engine" not in trace.knowledge_source_types, "research kullanılmamalı"
            assert trace.route == "memory_extractive", f"memory_extractive olmalı, got {trace.route}"
        finally:
            engine.shutdown()


def test_transaction_reasoning_context():
    """Vadeli mal aldım → transaction problem type, concepts."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = _make_engine(tmp)
        try:
            engine.cevap_ver("Vadeli mal aldım, muhasebe açısından ne oldu?")
            trace = engine.brain.last_trace
            assert trace.accounting_reasoning_used, "Reasoning context kullanılmalı"
            assert trace.problem_type == "transaction", f"transaction/unknown olmalı, got {trace.problem_type}"
            assert len(trace.concept_ids) > 0, "concept_ids dolu olmalı"
            assert "learning_store" in trace.knowledge_source_types, "learning_store kullanılmalı"
        finally:
            engine.shutdown()


def test_current_fact_reasoning_context():
    """2026 SGK prim tavanı → current_fact_needed TRUE, truth boundary."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = _make_engine(tmp)
        try:
            engine.cevap_ver("2026 SGK prime esas kazanç üst sınırı nedir?")
            trace = engine.brain.last_trace
            assert trace.accounting_reasoning_used, "Reasoning context kullanılmalı"
            assert trace.problem_type == "current_fact", f"current_fact olmalı, got {trace.problem_type}"
            assert trace.current_fact_needed is True, "current_fact_needed TRUE olmalı"
            assert "fact_registry" in trace.knowledge_source_types, "fact_registry kullanılmalı"
            assert trace.route == "not_found_offline", f"not_found_offline olmalı, got {trace.route}"
        finally:
            engine.shutdown()
