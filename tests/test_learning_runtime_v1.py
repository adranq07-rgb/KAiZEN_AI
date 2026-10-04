"""Real engine wiring and safety; every persistent store is temporary."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from accounting.retriever import Retriever, Evidence
from config.config_manager import ConfigManager
from core.ai.embedding_cache import EmbeddingCache
from core.ai.offline_provider import OfflineProvider
from core.engine import KaizenEngine
from tests.doubles import NullExperienceMemory


class Embeddings:
    model_name = "test-model"
    def __init__(self):
        self.calls = 0
    def is_ready(self):
        return True
    def embed(self, text):
        self.calls += 1
        return [1.0, 0.0] if "bir" in text else [0.0, 1.0]


def test_hybrid_cache_and_failure_preserve_lexical_candidates():
    with tempfile.TemporaryDirectory() as tmp:
        client = Embeddings()
        r = Retriever(object(), accounting_brain=object(), embedding_client=client,
                      embedding_cache=EmbeddingCache(Path(tmp)/"cache.db"), hybrid_enabled=True)
        items = [Evidence("site", "ikinci", "iki"), Evidence("site", "ilk", "bir")]
        assert r._semantic_rerank("bir soru", items)[0] is items[1]
        calls = client.calls
        assert r._semantic_rerank("bir soru", items)[0] is items[1]
        assert client.calls == calls
        with patch.object(client, "is_ready", side_effect=RuntimeError("down")):
            assert r._semantic_rerank("soru", items) == items
        assert r._cosine([float("nan")], [1.0]) is None


def _config():
    config = ConfigManager()
    config.config["learning"].update(learning_brain_enabled=True,
        experience_lifecycle_enabled=True, experience_advice_enabled=True,
        runtime_learning_enabled=True)
    config.config["retrieval"] = {"hybrid_enabled": True}
    return config


def test_engine_runtime_learning_transfer_feedback_and_truth_boundary():
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(data_dir=Path(tmp)/"data", log_dir=Path(tmp)/"logs",
                              provider=OfflineProvider(), config=_config(),
                              experience_memory=NullExperienceMemory())
        try:
            assert engine.brain.brain.retriever.hybrid_enabled
            first = engine.cevap_ver("Stok değerleme yöntemleri nedir?")
            trace = engine.brain.last_trace
            assert first and trace.experience_id and trace.reflection_id and trace.learned_principle_id
            assert not trace.experience_reusable
            effect = engine.brain.record_feedback("Stok değerleme yöntemleri nedir?", True)
            assert effect["applied"]
            engine.cevap_ver("Mizan nedir?")
            second = engine.brain.last_trace
            assert second.strategy_source == "learned_principle"
            assert second.strategy_experience_ids
            assert not second.used_model  # offline extractive route doesn't call a model
            engine.brain.record_feedback("Stok değerleme yöntemleri nedir?", False)
            engine.cevap_ver("Mizan nedir?")
            assert engine.brain.last_trace.strategy_source != "learned_principle"
            engine.accounting_agent.learn("12 + 7", "", "999")
            answer = engine.cevap_ver("12 + 7")
            assert "19" in answer and "999" not in answer
            assert engine.brain.last_trace.route == "arithmetic"
            assert engine.brain.last_trace.deterministic_tool == "arithmetic"
            assert engine.brain.last_trace.experience_id
        finally:
            assert engine.shutdown()


def test_engine_optional_store_failure_keeps_exact_answer():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("core.engine.ReflectionStore", side_effect=OSError("unavailable")):
            engine = KaizenEngine(data_dir=Path(tmp)/"data", log_dir=Path(tmp)/"logs",
                                  provider=OfflineProvider(), config=_config(),
                                  experience_memory=NullExperienceMemory())
        try:
            assert "19" in engine.cevap_ver("12 + 7")
            assert "learning" in engine.component_failures
        finally:
            engine.shutdown()


def test_semantic_ranking_cannot_admit_irrelevant_sources():
    class Sites:
        def search(self, *args, **kwargs):
            return [{"content": "Elma ağacının budanması ilkbaharda yapılır.",
                     "source_name": "official", "title": "unrelated", "url": "https://example.gov.tr"}]
    client = Embeddings()
    retriever = Retriever(object(), Sites(), accounting_brain=object(),
                          embedding_client=client, hybrid_enabled=True)
    assert retriever._site_evidence("Kurumlar vergisi oranı", 3) == []
    assert client.calls == 0


def test_embedding_cache_version_model_and_numeric_separation():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/"cache.db"
        cache = EmbeddingCache(path)
        cache.put("a", "  KDV  yüzde 4.5 ", [1.0, 0.0])
        assert cache.get("a", "kdv yüzde 4.5") == [1.0, 0.0]
        assert cache.get("a", "kdv yüzde 45") is None
        assert cache.get("b", "kdv yüzde 4.5") is None
        assert EmbeddingCache(path, cache_version=cache.cache_version + 1).get("a", "kdv yüzde 4.5") is None


def test_current_fact_cannot_come_from_correction_cognee_or_model():
    from tests.test_kaizen_brain_research_engine import _FakeSearchProvider, _FakeFetcher
    class PoisonMemory(NullExperienceMemory):
        def recall(self, *args, **kwargs):
            raise AssertionError("current facts must not consult raw experience")
    class PoisonModel:
        def ask(self, message):
            raise AssertionError("current facts must not be invented by a model")
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(data_dir=Path(tmp)/"data", log_dir=Path(tmp)/"logs",
            provider=PoisonModel(), config=_config(), experience_memory=PoisonMemory())
        try:
            engine.brain._search_provider = _FakeSearchProvider(results=[])
            engine.brain._research_fetcher = _FakeFetcher({})
            question = "2026 SGK prim tavanı nedir?"
            engine.cevap_ver("düzelt: " + question + " => 999.999.999 TL")
            answer = engine.cevap_ver(question)
            assert "999.999.999" not in answer
            assert engine.brain.last_route == "not_found_offline"
            assert engine.brain.last_trace.model_calls == 0
        finally:
            engine.shutdown()


def test_exact_answers_never_trigger_background_generative_memory():
    class Memory(NullExperienceMemory):
        def __init__(self): self.calls = []
        def remember(self, text):
            self.calls.append(text)
            return {"ok": True}
    memory = Memory()
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(data_dir=Path(tmp)/"data", log_dir=Path(tmp)/"logs",
            provider=OfflineProvider(), config=_config(), experience_memory=memory)
        engine.cevap_ver("12 + 7")
        assert engine.shutdown()
        assert not memory.calls
        assert engine.brain.last_trace.experience_id  # deterministic structural memory still learns


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_cognee_failure_timeout_redaction_and_duplicates():
    import asyncio
    from memory.cognee_memory import CogneeMemory
    from tests.test_cognee_memory import _FakeCognee
    from security.redaction import redact
    secret = "api_key=SUPER_SECRET_VALUE Bearer TOKEN_TO_HIDE sk-abcdefghijklmnopqrst"
    assert not any(s in redact(secret) for s in ("SUPER_SECRET_VALUE", "TOKEN_TO_HIDE", "abcdefghijklmnopqrst"))
    with tempfile.TemporaryDirectory() as tmp:
        memory = CogneeMemory(settings={"enabled": True, "write_timeout": .01}, storage_dir=tmp)
        fake = _FakeCognee()
        memory._cognee = fake
        assert memory.remember(secret)["ok"]
        assert "SUPER_SECRET_VALUE" not in fake.calls[0][1]
        assert memory.remember(secret)["status"] == "duplicate"
        assert len(fake.calls) == 1
        async def slow(*args, **kwargs): await asyncio.sleep(.2)
        with patch.object(fake, "remember", slow):
            assert memory.remember("different text")["error"] == "TimeoutError"
        with patch.object(fake, "recall", side_effect=RuntimeError("SECRET_ERROR")):
            failure = memory.recall("question")
            assert not failure["ok"] and failure["results"] == []
            assert "SECRET_ERROR" not in str(failure)


def test_policy_provenance_survives_restart_and_repeated_approval_is_not_extra_support():
    from learning.runtime_learning import RuntimeLearning
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(data_dir=Path(tmp)/"data", log_dir=Path(tmp)/"logs",
            provider=OfflineProvider(), config=_config(), experience_memory=NullExperienceMemory())
        q = "Stok değerleme yöntemleri nedir?"
        try:
            engine.cevap_ver(q)
            for _ in range(4): engine.cevap_ver("onayla: " + q)
            restarted = RuntimeLearning(engine.runtime_learning.db_path)
            advice = restarted.advise("Mizan nedir?", "accounting")
            assert advice.applied and advice.support == 1 and advice.confidence == "medium"
            engine.cevap_ver("düzelt: " + q + " => SECRET_CORRECTION_DO_NOT_STORE")
            assert not restarted.advise("Mizan nedir?", "accounting").applied
            assert b"SECRET_CORRECTION_DO_NOT_STORE" not in restarted.db_path.read_bytes()
        finally:
            engine.shutdown()
