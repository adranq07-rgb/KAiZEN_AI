"""Regression tests for runtime wiring; live acceptance is recorded separately."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from accounting.facts import FactRegistry
from accounting.retriever import Evidence, Retriever
from accounting.site_store import SiteStore
from core.kaizen_brain import KaizenBrain
from memory.brain_manager import BrainManager
from tests.doubles import NullExperienceMemory


def test_stable_consistency_is_not_current_amount():
    assert not KaizenBrain.needs_current_research(
        "Muhasebede dönemsellik ve tutarlılık kavramlarını birlikte açıkla")
    assert KaizenBrain.needs_current_research("2026 gecikme zammı oranı nedir?")


def test_strict_accounting_does_not_retry_provider_without_evidence():
    from tests.test_kaizen_brain import FakeProvider, FakeAccountingAgent
    with tempfile.TemporaryDirectory() as folder:
        provider = FakeProvider("Ungrounded accounting answer")
        manager = BrainManager(experience_memory=NullExperienceMemory(), log_dir=folder)
        brain = KaizenBrain(provider, FakeAccountingAgent(), brain_manager=manager, strict_fact_safety=True)
        with patch.object(brain, "_from_memory", return_value=(None, False)):
            answer = brain.answer("Muhasebede dönemsellik ve tutarlılığı birlikte açıkla")
        assert provider.calls == 0, "Missing grounded answer must not trigger a raw model retry"
        assert brain.last_route == "not_found_offline"
        assert "uydurmayacağım" in answer


def test_calendar_year_does_not_become_calculation_amount():
    brain = KaizenBrain.__new__(KaizenBrain)
    # Returning before tool dispatch proves no calculator can consume the year.
    assert brain._exact_tools("2026 gecikme zammı oranı nedir?") is None


def test_pending_and_wrong_year_cannot_be_verified_answers():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "sites.sqlite3"
        sites = SiteStore(db)
        sites.upsert_page(
            url="https://www.alomaliye.com/2026-test", source_name="Alomaliye",
            title="Synthetic fixture", effective_year=2026, published_at="2026-01-05",
            content="2026 yılında fatura düzenleme sınırı 11.111 TL olarak uygulanır.",
        )
        facts = FactRegistry(db)
        facts.rebuild(sites)
        manager = BrainManager(facts=facts, experience_memory=NullExperienceMemory(), log_dir=folder)
        assert manager.verified_fact_answer("2026 fatura düzenleme sınırı nedir?")
        assert manager.verified_fact_answer("2026 fatura düzenleme sınırı nedir?", strict=True) is None
        assert manager.verified_fact_answer("2027 fatura düzenleme sınırı nedir?", strict=True) is None
        assert facts.answer("Fatura düzenleme sınırı nedir?", current_year=2027, verified_only=True) is None


def test_course_candidates_reach_reranker_and_its_output_is_consumed():
    first = Evidence("ders", "first", "first text")
    second = Evidence("ders", "second", "second text")
    retriever = Retriever(None)
    with patch.object(retriever, "_course_evidence", return_value=[first, second]), \
         patch.object(retriever, "_site_evidence", return_value=[]), \
         patch.object(retriever, "_semantic_rerank", return_value=[second, first]) as rerank:
        result = retriever.gather("query", "accounting")
        assert rerank.call_args.args == ("query", [first, second])
        assert result == [second, first]
        assert retriever.last_metrics["lexical_candidate_count"] == 2
