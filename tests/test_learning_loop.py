"""KAIZEN — Learning Loop fazı: Reflection/Experience GERÇEK cevap yaşam döngüsüne bağlı.

Kapsam (iş emri): Reflection lifecycle, onayla: -> pozitif strateji sonucu, düzelt: -> negatif
strateji sonucu, FACT sızıntısı engeli, strateji transferi, NEGATİF transfer, yanlış geri
bildirimin sistemi zehirleyememesi, research -> öğrenme metadata'sı, deterministik önceliğin
korunması. GERÇEK AĞ YOK (test double'lar), tüm depolar geçici klasörde."""
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from accounting.retriever import says_not_found  # noqa: F401  (import sağlığı)
from core.commands import CommandHandler
from core.kaizen_brain import KaizenBrain
from learning.experience_meta import ExperienceMeta, _FACT_LIKE
from learning.experience_model import (
    Experience, ExperienceModelError, OUTCOME_FAILURE, OUTCOME_SUCCESS, VERIFICATION_NONE,
)
from learning.reflection_lifecycle import ReflectionLifecycle, question_key, _clean_labels
from learning.reflection_store import ReflectionStore
from learning.strategy_advisor import ADVICE_HIGH, ADVICE_MEDIUM, StrategyAdvisor
from learning.strategy_catalog import (
    PERIOD_SEPARATION, PRINCIPLE_GROUNDED, RESEARCH_FIRST, STRATEGIES,
)
from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds
from research.fetcher import FetchOutcome
from search.provider import SearchOutcome, SearchResult, STATUS_OK
from tests.doubles import NullExperienceMemory
from tests.test_kaizen_brain_research_engine import (
    FakeAccountingAgent, FakeProvider, _FakeFetcher, _FakeSearchProvider, _html, _sr,
)

RESEARCH_Q = "2026 SGK prim tavanı nedir?"
PRINCIPLE_Q_A = "Stok değerleme yöntemleri nedir?"
PRINCIPLE_Q_B = "Mizan nedir?"   # FARKLI kelimeler, AYNI yapı (kalıcı muhasebe kavramı)


class _RecordingProvider:
    def __init__(self, reply="Kaynağa dayalı cevap.\n\nSONUÇ: yerel ders notuna göre açıklandı."):
        self.reply, self.prompts = reply, []

    def ask(self, prompt):
        self.prompts.append(prompt)
        return self.reply


class _CorrectingAgent(FakeAccountingAgent):
    def learn(self, question, wrong_answer, correct_answer, user_note=None):
        return "Kaizen: Duzeltme kaydedildi."


def _supported_search(question=RESEARCH_Q):
    # 3 farklı resmi kaynak URL'si aynı sorgu için - SUPPORTED (verified) için 3 kaynak gerekir
    urls = (
        "https://www.sgk.gov.tr/duyuru/2026",
        "https://www.resmigazete.gov.tr/sgk-2026",
        "https://www.mevzuat.gov.tr/sgk-prim-2026",
    )
    provider = _FakeSearchProvider(results=[_sr(u, question) for u in urls])
    fetcher = _FakeFetcher({
        urls[0]: FetchOutcome(
            status="FETCH_OK", url=urls[0], final_url=urls[0],
            content_type="text/html; charset=utf-8",
            body=_html("2026 yılı için SGK prim tavanı 750.000 TL'dir.")),
        urls[1]: FetchOutcome(
            status="FETCH_OK", url=urls[1], final_url=urls[1],
            content_type="text/html; charset=utf-8",
            body=_html("Resmi Gazete: 2026 SGK prim tavanı 750.000 TL olarak ilan edildi.")),
        urls[2]: FetchOutcome(
            status="FETCH_OK", url=urls[2], final_url=urls[2],
            content_type="text/html; charset=utf-8",
            body=_html("Mevzuat: SGK prim tavanı 2026 için 750.000 TL'dir.")),
    })
    return provider, fetcher


def _brain(tmp, engine=False, provider=None, fetcher=None, llm=None, accounting=None,
           lifecycle=True, advisor=True, facts=None):
    store = LearningStore(Path(tmp) / "learning.sqlite3")
    load_seeds(store)
    reflections = ReflectionStore(Path(tmp) / "reflections.sqlite3")
    brain = KaizenBrain(
        llm or _RecordingProvider(), accounting or _CorrectingAgent(),
        brain_manager=BrainManager(
            learning_store=store, experience_memory=NullExperienceMemory(), log_dir=tmp, facts=facts,
        ),
        research_engine_enabled=engine, search_provider=provider, research_fetcher=fetcher,
        reflection_lifecycle=ReflectionLifecycle(reflections) if lifecycle else None,
        strategy_advisor=StrategyAdvisor(reflections) if advisor else None,
    )
    return brain, reflections


def _only_record(reflections, key_question):
    rid = reflections.find_latest_by_question_key(question_key(key_question))
    assert rid is not None
    return rid, reflections.get(rid), reflections.get_meta(rid)


def _handler(brain):
    class _Engine:
        pass
    engine = _Engine()
    engine.brain, engine.cards, engine.accounting_agent = brain, object(), brain.accounting_agent
    return CommandHandler(engine)


def _learning_columns_dump(reflections):
    """Öğrenme kayıtlarının FACT taşıyabilecek TÜM metin sütunları (id/hash/zaman hariç)."""
    with closing(sqlite3.connect(reflections.db_path)) as c:
        rows = c.execute(
            """SELECT r.problem_signature, r.selected_principle, r.strategy, r.tools_used,
                      r.evidence_used, r.outcome, r.verification, m.route, m.question_kind,
                      m.strategy_kind, m.research_status, m.consensus_status, m.provider_health,
                      m.confidence, m.provenance
               FROM reflections r JOIN reflection_meta m ON m.id = r.id"""
        ).fetchall()
    return " ".join(str(v) for row in rows for v in row)


# ----------------------------------------------------------------------------- yaşam döngüsü
def test_reflection_lifecycle_records_structural_experience_never_answer_or_fact():
    with tempfile.TemporaryDirectory() as tmp:
        provider, fetcher = _supported_search()
        brain, reflections = _brain(tmp, engine=True, provider=provider, fetcher=fetcher)
        answer = brain.answer(RESEARCH_Q)
        assert "750.000 TL" in answer                      # cevap kullanıcıya gitti...
        rid, exp, meta = _only_record(reflections, RESEARCH_Q)
        assert exp.strategy == RESEARCH_FIRST and meta.strategy_kind == RESEARCH_FIRST
        assert exp.outcome == OUTCOME_SUCCESS and exp.verification == "cross_checked"
        assert exp.user_approved is False and exp.reusable is False      # D3: otomatik güven YOK
        assert meta.research_used and meta.research_status == "SUPPORTED"
        assert meta.consensus_status == "agreed" and meta.provenance == "auto:trace"
        assert meta.independent_evidence_count >= 1 and meta.confidence in ("medium", "high")
        assert brain.last_trace.reflection_written is True and brain.last_trace.experience_candidate is True
        dump = _learning_columns_dump(reflections)
        assert "750" not in dump and "TL" not in dump and "2026" not in dump   # ...ama öğrenmeye SIZMADI
        assert not _FACT_LIKE.search(dump), dump
        assert reflections.count() == 1
    print("KAIZEN LEARNING LOOP: REFLECTION YASAM DONGUSU (YAPI KAYDI, FACT YOK) TESTI: BASARILI")


def test_lifecycle_skips_deterministic_routes_and_never_touches_facts_or_correction():
    with tempfile.TemporaryDirectory() as tmp:
        brain, reflections = _brain(tmp)
        brain.answer("125 çarpı 8 kaç eder?")
        assert brain.last_route == "calculator"
        assert reflections.count() == 0                     # deterministik katman öğrenmeye konu değil
        assert brain.last_trace.reflection_written is None  # denenmedi -> uydurulmaz
        assert brain.last_trace.experience_advice is None
    print("KAIZEN LEARNING LOOP: DETERMINISTIK ROTA KAYIT DISI TESTI: BASARILI")


# ------------------------------------------------------------------- onayla: / düzelt:
def test_onayla_records_positive_outcome_and_only_then_strategy_becomes_reusable():
    with tempfile.TemporaryDirectory() as tmp:
        provider, fetcher = _supported_search()
        brain, reflections = _brain(tmp, engine=True, provider=provider, fetcher=fetcher)
        brain.answer(RESEARCH_Q)
        rid, before, _ = _only_record(reflections, RESEARCH_Q)
        assert before.reusable is False and before.user_approved is False

        reply = _handler(brain).handle(f"onayla: {RESEARCH_Q}")
        assert "yeniden kullanılabilir strateji" in reply and "FACT olarak kaydedilmedi" in reply
        _, after, meta = _only_record(reflections, RESEARCH_Q)
        assert after.user_approved is True and after.reusable is True
        assert after.outcome == OUTCOME_SUCCESS and after.verification == "user_approved"
        assert meta.positive_count == 1 and meta.negative_count == 0 and meta.provenance == "user_feedback"
        assert brain.last_feedback_effect["reusable"] is True
        assert not _FACT_LIKE.search(_learning_columns_dump(reflections))
    print("KAIZEN LEARNING LOOP: ONAYLA -> POZITIF STRATEJI SONUCU TESTI: BASARILI")


def test_onayla_never_makes_refusal_or_strategyless_answer_reusable():
    with tempfile.TemporaryDirectory() as tmp:
        # Research yok/başarısız -> 'bulamadım' (refused): onay reusable YAPMAZ
        brain, reflections = _brain(tmp, llm=_RecordingProvider("Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod)"),
                                    accounting=_CorrectingAgent(reply="Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod)"))
        brain.answer("Bu işlem hangi hesaba gider: ofis kirası ödedik?")
        assert brain.last_route == "not_found_offline"
        _, exp, meta = _only_record(reflections, "Bu işlem hangi hesaba gider: ofis kirası ödedik?")
        assert exp.outcome == "refused" and meta.strategy_kind == ""
        _handler(brain).handle("onayla: Bu işlem hangi hesaba gider: ofis kirası ödedik?")
        _, exp2, _ = _only_record(reflections, "Bu işlem hangi hesaba gider: ofis kirası ödedik?")
        assert exp2.user_approved is True and exp2.reusable is False and exp2.outcome == "refused"
    print("KAIZEN LEARNING LOOP: RED/STRATEJISIZ CEVAP ONAYLA ILE REUSABLE OLMAZ TESTI: BASARILI")


def test_duzelt_records_negative_outcome_revokes_reusable_and_is_sticky():
    with tempfile.TemporaryDirectory() as tmp:
        provider, fetcher = _supported_search()
        brain, reflections = _brain(tmp, engine=True, provider=provider, fetcher=fetcher)
        brain.answer(RESEARCH_Q)
        handler = _handler(brain)
        handler.handle(f"onayla: {RESEARCH_Q}")
        assert _only_record(reflections, RESEARCH_Q)[1].reusable is True

        reply = handler.handle(f"düzelt: {RESEARCH_Q} => 400.000 TL")
        assert reply.startswith("Kaizen: Duzeltme kaydedildi.")     # mevcut düzeltme mekanizması aynen
        assert "strateji etkisi düşürüldü" in reply
        _, exp, meta = _only_record(reflections, RESEARCH_Q)
        assert exp.outcome == OUTCOME_FAILURE and exp.reusable is False and exp.user_approved is False
        assert meta.negative_count == 1
        # kullanıcının verdiği rakam öğrenme depolarına GİTMEDİ (FACT olarak doğrulanmadı)
        assert "400" not in _learning_columns_dump(reflections)

        # Olumsuz geri bildirim YAPIŞKAN: sonradan gelen onay başarıyı/reusable'ı geri getirmez
        handler.handle(f"onayla: {RESEARCH_Q}")
        _, exp2, meta2 = _only_record(reflections, RESEARCH_Q)
        assert exp2.outcome == OUTCOME_FAILURE and exp2.reusable is False and meta2.negative_count == 1
    print("KAIZEN LEARNING LOOP: DUZELT -> NEGATIF STRATEJI SONUCU (YAPISKAN) TESTI: BASARILI")


def test_commands_keep_legacy_strings_when_lifecycle_is_off_or_no_experience_exists():
    with tempfile.TemporaryDirectory() as tmp:
        brain, _ = _brain(tmp, lifecycle=False, advisor=False)
        handler = _handler(brain)
        assert handler.handle("düzelt: soru => cevap") == "Kaizen: Duzeltme kaydedildi."
        assert "bulamadım" in handler.handle("onayla: hiç sorulmamış bir soru")
        assert "Öğrenme:" not in handler.handle("onayla: hiç sorulmamış bir soru")
        brain2, _ = _brain(tempfile.mkdtemp())                            # yaşam döngüsü açık ama kayıt yok
        assert "Öğrenme:" not in _handler(brain2).handle("onayla: hiç sorulmamış bir soru")
        assert handler.handle("düzelt: soru => cevap") == "Kaizen: Duzeltme kaydedildi."
    print("KAIZEN LEARNING LOOP: KAPALI/KAYITSIZ DURUMDA ESKI KOMUT CIKTISI KORUNUR TESTI: BASARILI")


# ------------------------------------------------------------------ FACT sızıntı engeli
def test_fact_leakage_is_structurally_impossible_in_meta_and_labels():
    for bad in ("oran %20", "KDV 20", "2026", "1.500 TL", "18,5"):
        for field in ("route", "question_kind", "strategy_kind", "research_status", "consensus_status", "provider_health"):
            if not _FACT_LIKE.search(bad):
                continue
            try:
                ExperienceMeta(question_key="k", **{field: bad})
            except ExperienceModelError:
                continue
            raise AssertionError(f"{field}={bad!r} FACT benzeri değer kabul edildi")
    # kanıt etiketleri: FACT benzeri (yıl/tutar) olanlar ELENİR, alan adları kalır
    assert _clean_labels(("www.gib.gov.tr", "2026.example.com", "kaynak %20")) == ("www.gib.gov.tr",)
    # Experience'ın 10 alanlık D2 kontratı bu fazda DEĞİŞMEDİ (yeni bilgi ayrı ExperienceMeta'da)
    assert len(Experience.__dataclass_fields__) == 10
    # Strateji kataloğu SÜREÇ tarif eder: hiçbir rakam/oran/yıl içermez
    for spec in STRATEGIES.values():
        assert not re.search(r"\d|%", spec["guide"]), spec["guide"]
    print("KAIZEN LEARNING LOOP: FACT SIZINTISI ENGELI (YAPISAL) TESTI: BASARILI")


# ---------------------------------------------------------------------- strateji transferi
def test_strategy_transfers_to_a_structurally_similar_different_problem_without_facts():
    with tempfile.TemporaryDirectory() as tmp:
        llm = _RecordingProvider()
        brain, reflections = _brain(tmp, llm=llm)
        brain.answer(PRINCIPLE_Q_A)                                   # Problem A: kalıcı prensip, kanıtlı hafıza
        assert brain.last_route == "memory_grounded"
        assert _only_record(reflections, PRINCIPLE_Q_A)[2].strategy_kind == PRINCIPLE_GROUNDED
        assert not any("DENEYİM STRATEJİ İPUCU" in p for p in llm.prompts)   # onaysızken HİÇ yönlendirmez
        assert brain.last_trace.experience_reusable is None

        _handler(brain).handle(f"onayla: {PRINCIPLE_Q_A}")
        llm.prompts.clear()
        brain.answer(PRINCIPLE_Q_B)                                   # Problem B: farklı kelime, aynı YAPI
        assert brain.last_route == "memory_grounded"
        hint_prompts = [p for p in llm.prompts if "DENEYİM STRATEJİ İPUCU" in p]
        assert len(hint_prompts) == 1
        hint = hint_prompts[0].split("[DENEYİM STRATEJİ İPUCU", 1)[1]
        assert not re.search(r"%|\d", hint), hint          # ipucu SÜREÇ tarifidir: rakam/oran yok
        assert "kaynak yerine geçmez" in hint
        assert brain.last_trace.experience_reusable is True
        assert brain.last_trace.experience_advice == PRINCIPLE_GROUNDED
        # Yönlendirme sonrası cevap route'u/güveni DEĞİŞMEZ (SUPPORTED kalır, VERIFIED olmaz)
        assert brain.last_trace.confidence == "SUPPORTED"
    print("KAIZEN LEARNING LOOP: STRATEJI TRANSFERI (FARKLI PROBLEM, FACT YOK) TESTI: BASARILI")


def test_current_fact_strategy_advice_carries_process_only_and_can_trigger_research():
    with tempfile.TemporaryDirectory() as tmp:
        provider, fetcher = _supported_search()
        brain, reflections = _brain(tmp, engine=True, provider=provider, fetcher=fetcher)
        brain.answer(RESEARCH_Q)
        _handler(brain).handle(f"onayla: {RESEARCH_Q}")
        advisor = StrategyAdvisor(reflections)
        advice = advisor.advise("Damga vergisi oranı bu yıl ne kadar?", "accounting")
        assert advice.applied and advice.strategy_kind == RESEARCH_FIRST and advice.triggers_research
        assert advice.confidence == ADVICE_MEDIUM and advice.support == 1
        assert not re.search(r"\d|%", advice.guide)
        assert "ASLA" not in advice.guide  # katalog metni sade süreç tarifi
    print("KAIZEN LEARNING LOOP: GUNCEL-FACT STRATEJISI SUREC-YALNIZ TESTI: BASARILI")


def test_negative_transfer_is_rejected_for_mismatched_structure_and_unapproved_experience():
    with tempfile.TemporaryDirectory() as tmp:
        store = ReflectionStore(Path(tmp) / "r.sqlite3")
        advisor = StrategyAdvisor(store)

        def put(kind, strategy, key, approved=False, reusable=False, pos=0, neg=0, outcome=OUTCOME_SUCCESS):
            exp = Experience(problem_signature=f"accounting|{kind}|-", selected_principle=None,
                             strategy=strategy or "route:x", tools_used=(), evidence_used=(),
                             outcome=outcome, verification=VERIFICATION_NONE,
                             user_approved=approved, reusable=reusable)
            meta = ExperienceMeta(question_key=key, question_kind=kind, strategy_kind=strategy,
                                  positive_count=pos, negative_count=neg)
            return store.record(exp, meta)

        # 1) onaylanmamış (reusable olmayan) deneyim ASLA yönlendirmez
        put("accounting_principle", PRINCIPLE_GROUNDED, "k1")
        assert not advisor.advise("Envanter nedir?", "accounting").applied
        # 2) 'dönem ayrımı' stratejisi güncel-FACT sorusuna UYGULANMAZ (yapı uyuşmazlığı)
        put("current_fact", PERIOD_SEPARATION, "k2", approved=True, reusable=True, pos=1)
        advice = advisor.advise("2026 damga vergisi oranı kaç?", "accounting")
        assert not advice.applied and advice.rejected_reason == "negative_transfer_structure_mismatch"
        # 3) muhasebe dışı alan: hiç çalışmaz
        assert advisor.advise("Excel'de düşeyara nasıl kullanılır?", "office").rejected_reason == "domain_not_supported"
    print("KAIZEN LEARNING LOOP: NEGATIF TRANSFER REDDI TESTI: BASARILI")


def test_wrong_feedback_cannot_poison_the_system_repeated_approval_does_not_inflate():
    with tempfile.TemporaryDirectory() as tmp:
        store = ReflectionStore(Path(tmp) / "r.sqlite3")
        advisor = StrategyAdvisor(store)
        exp = Experience(problem_signature="accounting|accounting_principle|-", selected_principle=None,
                         strategy=PRINCIPLE_GROUNDED, tools_used=(), evidence_used=(),
                         outcome=OUTCOME_SUCCESS, verification=VERIFICATION_NONE)
        rid = store.record(exp, ExperienceMeta(question_key="a", question_kind="accounting_principle",
                                               strategy_kind=PRINCIPLE_GROUNDED))
        for _ in range(6):                                   # tekrarlanan onay spam'i
            store.apply_feedback(rid, True, allow_reusable=True)
        advice = advisor.advise("Envanter nedir?", "accounting")
        assert advice.applied and advice.net_score == 1 and advice.confidence == ADVICE_MEDIUM  # şişmez

        # Aynı stratejinin BAŞKA bir kaydına gelen tek olumsuz geri bildirim etkiyi düşürür/kapatır
        rid2 = store.record(exp, ExperienceMeta(question_key="b", question_kind="accounting_principle",
                                                strategy_kind=PRINCIPLE_GROUNDED))
        store.apply_feedback(rid2, False)
        advice2 = advisor.advise("Envanter nedir?", "accounting")
        assert not advice2.applied and advice2.rejected_reason == "negative_feedback_reduced_influence"
        # Geri bildirim yalnız İLGİLİ kaydı etkiledi: ilk kayıt hâlâ reusable
        assert store.get(rid).reusable is True and store.get(rid2).reusable is False
    print("KAIZEN LEARNING LOOP: YANLIS GERI BILDIRIM SISTEMI ZEHIRLEYEMEZ TESTI: BASARILI")


def test_high_confidence_needs_multiple_distinct_approved_questions():
    with tempfile.TemporaryDirectory() as tmp:
        store = ReflectionStore(Path(tmp) / "r.sqlite3")
        advisor = StrategyAdvisor(store)
        for i in range(3):
            exp = Experience(problem_signature="accounting|accounting_principle|-", selected_principle=None,
                             strategy=PRINCIPLE_GROUNDED, tools_used=(), evidence_used=(),
                             outcome=OUTCOME_SUCCESS, verification=VERIFICATION_NONE)
            rid = store.record(exp, ExperienceMeta(question_key=f"q{i}", question_kind="accounting_principle",
                                                   strategy_kind=PRINCIPLE_GROUNDED))
            store.apply_feedback(rid, True, allow_reusable=True)
        advice = advisor.advise("Envanter nedir?", "accounting")
        assert advice.confidence == ADVICE_HIGH and advice.support == 3 and advice.net_score == 3
    print("KAIZEN LEARNING LOOP: YUKSEK GUVEN COKLU BAGIMSIZ ONAY GEREKTIRIR TESTI: BASARILI")


# ------------------------------------------------------------ deterministik/fact önceliği
def test_experience_never_overrides_deterministic_layers_or_user_correction():
    with tempfile.TemporaryDirectory() as tmp:
        provider, fetcher = _supported_search()
        brain, reflections = _brain(tmp, engine=True, provider=provider, fetcher=fetcher)
        brain.answer(RESEARCH_Q)
        _handler(brain).handle(f"onayla: {RESEARCH_Q}")
        calls_before = provider.calls
        answer = brain.answer("300 TL'nin yüzde kaçı 60 TL eder?")
        assert brain.last_route == "calculator" and "%20" in answer
        assert provider.calls == calls_before                    # araştırma/deneyim devreye GİRMEDİ
        assert brain.last_trace.experience_advice is None and brain.last_trace.research_status is None
        # kullanıcı düzeltmesi en yüksek öncelik: deneyim/araştırma cevabı ezemez
        brain.accounting_agent.learning_memory = type("M", (), {"get_all": lambda self: [
            {"question": RESEARCH_Q, "correct_answer": "KULLANICI CEVABI"}]})()
        assert "KULLANICI CEVABI" in brain.answer(RESEARCH_Q) and brain.last_route == "correction"
    print("KAIZEN LEARNING LOOP: ONCELIK SIRASI (DUZELTME/KESIN ARAC > DENEYIM) TESTI: BASARILI")


if __name__ == "__main__":
    test_reflection_lifecycle_records_structural_experience_never_answer_or_fact()
    test_lifecycle_skips_deterministic_routes_and_never_touches_facts_or_correction()
    test_onayla_records_positive_outcome_and_only_then_strategy_becomes_reusable()
    test_onayla_never_makes_refusal_or_strategyless_answer_reusable()
    test_duzelt_records_negative_outcome_revokes_reusable_and_is_sticky()
    test_commands_keep_legacy_strings_when_lifecycle_is_off_or_no_experience_exists()
    test_fact_leakage_is_structurally_impossible_in_meta_and_labels()
    test_strategy_transfers_to_a_structurally_similar_different_problem_without_facts()
    test_current_fact_strategy_advice_carries_process_only_and_can_trigger_research()
    test_negative_transfer_is_rejected_for_mismatched_structure_and_unapproved_experience()
    test_wrong_feedback_cannot_poison_the_system_repeated_approval_does_not_inflate()
    test_high_confidence_needs_multiple_distinct_approved_questions()
    test_experience_never_overrides_deterministic_layers_or_user_correction()
