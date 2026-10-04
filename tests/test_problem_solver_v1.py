"""Isolated behavior tests. Final acceptance is a separate real runtime run."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config_manager import ConfigManager
from core.ai.offline_provider import OfflineProvider
from core.engine import KaizenEngine
from tests.doubles import NullExperienceMemory


def make_config():
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


def test_case_1_mizan():
    """Mizan nedir? → definition, research False, source-backed."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(
            data_dir=Path(tmp) / "data",
            log_dir=Path(tmp) / "logs",
            provider=OfflineProvider(),
            config=make_config(),
            experience_memory=NullExperienceMemory(),
        )
        try:
            answer = engine.cevap_ver("Mizan nedir?")
            trace = engine.brain.last_trace
            assert trace.problem_type == "definition", f"problem_type=definition bekleniyordu, got {trace.problem_type}"
            assert trace.current_fact_needed is False, "current_fact_needed False olmalı"
            assert trace.used_research is False, "research False olmalı"
            assert "KAYNAKLAR" in answer or "Mizan" in answer, "answer Mizan bilgisi içermeli"
            assert trace.route == "memory_extractive", f"memory_extractive bekleniyordu, got {trace.route}"
        finally:
            engine.shutdown()


def test_case_2_vadeli_mal_aldim():
    """Vadeli mal aldım → transaction, source-backed concepts, provider fallback yok."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(
            data_dir=Path(tmp) / "data",
            log_dir=Path(tmp) / "logs",
            provider=OfflineProvider(),
            config=make_config(),
            experience_memory=NullExperienceMemory(),
        )
        try:
            answer = engine.cevap_ver("Vadeli mal aldım, muhasebe açısından ne oldu?")
            trace = engine.brain.last_trace
            assert trace.problem_type == "transaction", f"problem_type=transaction bekleniyordu, got {trace.problem_type}"
            assert len(trace.concept_ids) > 0, "concept_ids dolu olmalı"
            # Source-backed concepts: LearningStore'dan gelen kavramlar
            assert any("mal" in c.lower() or "ticari" in c.lower() or "stok" in c.lower()
                       for c in trace.concept_ids), "concept_ids muhasebe kavramları içermeli"
            assert trace.used_model is False, "provider fallback kullanılmadı"
            assert trace.route == "memory_grounded", f"memory_grounded bekleniyordu, got {trace.route}"
            assert "Ticari Mallar" in answer or "İndirilecek KDV" in answer, "answer muhasebe etkisini açıklamalı"
        finally:
            engine.shutdown()


def test_case_3_kdv_leak():
    """KDV oranı verilmediğinde unverified leak OLMAMALI."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(
            data_dir=Path(tmp) / "data",
            log_dir=Path(tmp) / "logs",
            provider=OfflineProvider(),
            config=make_config(),
            experience_memory=NullExperienceMemory(),
        )
        try:
            answer = engine.cevap_ver(
                "İşletme 10.000 TL + KDV tutarında ticari malı vadeli satın aldı. "
                "Muhasebe açısından işlemi açıkla ve kaydı oluştur."
            )
            trace = engine.brain.last_trace
            # KDV oranı doğrulanmamışsa answer "%20" içeremez
            answer_lower = answer.lower()
            leak = "%20" in answer_lower or "yüzde 20" in answer_lower or "yüzde20" in answer_lower
            assert not leak, "UNVERIFIED KDV LEAK: answer içinde %20 var"
            assert trace.current_fact_needed is True, "current_fact_needed True olmalı"
        finally:
            engine.shutdown()


def test_case_4_pesin_transfer():
    """Peşin mal aldım → same event family, different payment state."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(
            data_dir=Path(tmp) / "data",
            log_dir=Path(tmp) / "logs",
            provider=OfflineProvider(),
            config=make_config(),
            experience_memory=NullExperienceMemory(),
        )
        try:
            # Önce vadeli sor (context oluştur)
            engine.cevap_ver("Vadeli mal aldım, muhasebe açısından ne oldu?")
            # Sonra peşin sor
            answer = engine.cevap_ver("Bu kez aynı mal peşin alınsaydı muhasebe etkisi nasıl değişirdi?")
            trace = engine.brain.last_trace
            assert trace.problem_type == "transaction", f"problem_type=transaction bekleniyordu, got {trace.problem_type}"
            # Peşin: Kasa/Banka hesabı devreye girer
            context = trace.accounting_reasoning_context
            assert context["payment_state"] == "paid"
            effects = context["account_effects"]
            assert {e["account"] for e in effects if e.get("alternative_group")} == {"100", "102"}
            assert all(e["direction"] == "credit" and e["source"]["record_id"]
                       for e in effects if e.get("alternative_group"))
            assert "320 Satıcılar hesabına alacak" not in answer
            assert trace.route == "memory_grounded", f"memory_grounded bekleniyordu, got {trace.route}"
        finally:
            engine.shutdown()


def test_case_5_semantic_transfer():
    """Şirket stok için mal aldı, bedelini henüz satıcıya ödemedi."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(
            data_dir=Path(tmp) / "data",
            log_dir=Path(tmp) / "logs",
            provider=OfflineProvider(),
            config=make_config(),
            experience_memory=NullExperienceMemory(),
        )
        try:
            answer = engine.cevap_ver(
                "Şirket stok için mal aldı, bedelini henüz satıcıya ödemedi. "
                "Muhasebeci bu olayı nasıl değerlendirir?"
            )
            trace = engine.brain.last_trace
            assert trace.problem_type == "transaction", f"problem_type=transaction bekleniyordu, got {trace.problem_type}"
            assert len(trace.concept_ids) > 0, "concept_ids dolu olmalı"
            assert trace.route == "memory_grounded", f"memory_grounded bekleniyordu, got {trace.route}"
            assert "Ticari Mallar" in answer or "İndirilecek KDV" in answer, "answer muhasebe etkisini açıklamalı"
        finally:
            engine.shutdown()


def test_case_6_persistence():
    """Transaction sonrası reflection_meta'da reasoning context persist olmalı."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(
            data_dir=Path(tmp) / "data",
            log_dir=Path(tmp) / "logs",
            provider=OfflineProvider(),
            config=make_config(),
            experience_memory=NullExperienceMemory(),
        )
        try:
            answer = engine.cevap_ver("Vadeli mal aldım, muhasebe açısından ne oldu?")
            assert answer
            # Reflection store'dan son kaydı oku
            store = engine.reflection_lifecycle.store
            all_records = store.list_with_meta(None)
            assert len(all_records) > 0, "Reflection kaydı oluşturulmalı"
            latest_id, exp, meta = all_records[-1]
            # Yeni alanlar persist edilmeli
            reasoning = store.get_reasoning_meta(latest_id)
            assert reasoning, "get_reasoning_meta kayıt döndürmeli"
            assert reasoning['problem_type'], "reasoning problem_type içermeli"
            assert isinstance(reasoning['principle_ids'], list)
            engine.shutdown()
            engine = KaizenEngine(data_dir=Path(tmp) / "data", log_dir=Path(tmp) / "logs",
                                  provider=OfflineProvider(), config=make_config(),
                                  experience_memory=NullExperienceMemory())
            assert engine.reflection_store.get_reasoning_meta(latest_id) == reasoning
        finally:
            engine.shutdown()


def test_source_required_and_no_false_purchase():
    from core.accounting_reasoning import AccountantReasoningEngine
    assert not AccountantReasoningEngine().build_context(
        "Vadeli mal aldım", "accounting").event_type
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(data_dir=Path(tmp)/"data", log_dir=Path(tmp)/"logs",
                              provider=OfflineProvider(), config=make_config(),
                              experience_memory=NullExperienceMemory())
        try:
            for q in ("Kasadaki nakit bankaya yatırıldı, muhasebe kaydı nedir?",
                      "Mal almadım, stok sayımı yaptım.", "Aldığım malı satıcıya iade ettim.",
                      "Mal sattım, bedelini henüz almadım.", "Stok için mal sipariş ettim."):
                engine.cevap_ver(q)
                ctx = engine.brain.last_trace.accounting_reasoning_context
                assert not ctx or not ctx["event_type"], q
        finally:
            engine.shutdown()


def test_principle_failure_is_distinct_from_no_applicable_principle():
    from core.accounting_reasoning import AccountantReasoningEngine
    class BrokenRetriever:
        def retrieve(self, question):
            raise RuntimeError("unavailable")
    context = AccountantReasoningEngine(principle_retriever=BrokenRetriever()).build_context("Mizan nedir?", "accounting")
    assert context.principle_retrieval_status == "RETRIEVAL_FAILED"
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(data_dir=Path(tmp)/"data", log_dir=Path(tmp)/"logs",
                              provider=OfflineProvider(), config=make_config(),
                              experience_memory=NullExperienceMemory())
        try:
            ctx = engine.brain._reasoning_engine.build_context("Vadeli mal aldım", "accounting")
            assert ctx.principle_retrieval_status == "NONE_APPLICABLE"
            ctx = engine.brain._reasoning_engine.build_context("Aktif hesaplarda artış hangi tarafa borç mu alacak mı yazılır?", "accounting")
            assert ctx.principle_retrieval_status == "APPLIED" and ctx.relevant_principle_ids
            answer = engine.cevap_ver("Vadeli mal aldım; hangi tarafa borç mu alacak mı yazılır?")
            assert engine.brain.last_trace.principle_retrieval_status == "APPLIED"
            for pid in engine.brain.last_trace.principle_ids:
                assert engine.principle_registry.get(pid)["description"] in answer
        finally:
            engine.shutdown()


def test_legacy_reflection_migration_preserves_record():
    import sqlite3
    from learning.reflection_store import ReflectionStore
    from learning.experience_model import Experience
    from learning.experience_meta import ExperienceMeta
    with tempfile.TemporaryDirectory() as tmp:
        current = ReflectionStore(Path(tmp)/"current.sqlite3")
        rid = current.record(Experience(problem_signature="accounting:definition", selected_principle=None, strategy="route:memory_extractive", tools_used=(), evidence_used=(), outcome="unknown", verification="none"),
                             ExperienceMeta(question_key="old-question"))
        # Construct a genuinely old schema in a separate fixture, without dropping records.
        with sqlite3.connect(current.db_path) as src, sqlite3.connect(Path(tmp)/"legacy.sqlite3") as dst:
            schema = src.execute("SELECT sql FROM sqlite_master WHERE name='reflections'").fetchone()[0]
            dst.execute(schema)
            row = src.execute("SELECT * FROM reflections").fetchone()
            dst.execute("INSERT INTO reflections VALUES ("+",".join("?" for _ in row)+")",row)
            schema = src.execute("SELECT sql FROM sqlite_master WHERE name='reflection_meta'").fetchone()[0]
            schema = schema[:schema.index(",\n                    problem_type")] + ")"
            dst.execute(schema)
            row = src.execute("SELECT * FROM reflection_meta").fetchone()[:17]
            dst.execute("INSERT INTO reflection_meta VALUES ("+",".join("?" for _ in row)+")",row)
        src.close()
        dst.close()
        migrated = ReflectionStore(Path(tmp)/"legacy.sqlite3")
        assert migrated.get(rid).problem_signature == "accounting:definition"
        assert migrated.get_meta(rid).question_key == "old-question"
        assert migrated.get_reasoning_meta(rid)["concept_ids"] == []
        assert ReflectionStore(migrated.db_path).get(rid) == migrated.get(rid)
