"""Cevap-verme düzeltmesi (2026-10-03): resmî kaynak PARTIAL planında yanlışlıkla
current_fact_missing ile reddedilmesin; gerçekten yetersiz/çelişkili kanıtta red aynen sürsün.
Gerçek ağ YOK (test double)."""
import tempfile

from core.kaizen_brain import _format_research_result
from research.fetcher import FetchOutcome
from research.models import CONFLICTED, PARTIAL, Claim, ResearchResult
from search.provider import SearchOutcome, STATUS_OK
from tests.doubles import NullExperienceMemory
from tests.test_kaizen_brain_research_engine import (
    FakeAccountingAgent, _FakeFetcher, _brain, _cleanup, _html, _sr, _workspace,
)

Q = "2026 SGK prim tavanı nedir?"
URL = "https://www.sgk.gov.tr/duyuru/2026"


class _MainQueryOnlyProvider:
    """Yalnız kullanıcının sorusunun KENDİSİ için sonuç döner; resmî-domain / Resmî Gazete
    açıları boş kalır -> engine genel durumu PARTIAL olur (gerçek PC'deki durumun aynısı).
    YENİ KURAL: 3 kaynak gerekir SUPPORTED için. Bu test 3 resmi kaynak sağlar."""
    def __init__(self):
        self.calls = 0

    def search(self, query, options=None):
        self.calls += 1
        # 3 farklı resmi kaynak URL'si aynı sorgu için
        if query == Q:
            results = (
                _sr("https://www.sgk.gov.tr/duyuru/2026", query),
                _sr("https://www.resmigazete.gov.tr/sgk-2026", query),
                _sr("https://www.mevzuat.gov.tr/sgk-prim-2026", query),
            )
        else:
            results = ()
        return SearchOutcome(results=results, query=query, status=STATUS_OK)


def _fetcher():
    return _FakeFetcher({
        "https://www.sgk.gov.tr/duyuru/2026": FetchOutcome(
            status="FETCH_OK", url="https://www.sgk.gov.tr/duyuru/2026", final_url="https://www.sgk.gov.tr/duyuru/2026",
            content_type="text/html; charset=utf-8", body=_html("2026 yılı için SGK prim tavanı 750.000 TL'dir.")),
        "https://www.resmigazete.gov.tr/sgk-2026": FetchOutcome(
            status="FETCH_OK", url="https://www.resmigazete.gov.tr/sgk-2026", final_url="https://www.resmigazete.gov.tr/sgk-2026",
            content_type="text/html; charset=utf-8", body=_html("Resmi Gazete: 2026 SGK prim tavanı 750.000 TL olarak ilan edildi.")),
        "https://www.mevzuat.gov.tr/sgk-prim-2026": FetchOutcome(
            status="FETCH_OK", url="https://www.mevzuat.gov.tr/sgk-prim-2026", final_url="https://www.mevzuat.gov.tr/sgk-prim-2026",
            content_type="text/html; charset=utf-8", body=_html("Mevzuat: SGK prim tavanı 2026 için 750.000 TL'dir.")),
    })


def test_partial_plan_with_official_supported_primary_claim_gives_sourced_answer():
    root, token = _workspace()
    db = root / f"kb_ar_partial_{token}.sqlite3"
    try:
        accounting = FakeAccountingAgent()
        brain = _brain(db, accounting, research_engine_enabled=True, search_provider=_MainQueryOnlyProvider(),
                       research_fetcher=_fetcher(), strict_fact_safety=True)
        answer = brain.answer(Q)
        t = brain.last_trace
        assert t.research_status == "PARTIAL", t.research_status          # engine kararı DEĞİŞMEDİ
        assert brain.last_route == "research", brain.last_route
        assert t.refusal_reason is None
        assert "750.000 TL" in answer and "sgk.gov.tr" in answer and "KAYNAKLAR:" in answer
        assert "NOT:" in answer                                          # eksik açılar dürüstçe belirtildi
        assert "VERIFIED" not in answer and "uydurmayacağım" not in answer
        assert accounting.calls == 0
    finally:
        _cleanup(db)


def test_partial_without_official_content_still_refuses():
    root, token = _workspace()
    db = root / f"kb_ar_refuse_{token}.sqlite3"
    try:
        class _Empty:
            def search(self, query, options=None):
                return SearchOutcome(results=(), query=query, status=STATUS_OK)
        brain = _brain(db, FakeAccountingAgent(), research_engine_enabled=True, search_provider=_Empty(),
                       research_fetcher=_FakeFetcher({}), strict_fact_safety=True)
        answer = brain.answer(Q)
        assert brain.last_route == "not_found_offline" and "uydurmayacağım" in answer
        assert brain.last_trace.refusal_reason == "current_fact_missing"
    finally:
        _cleanup(db)


def _result(status, claims, conflicts=()):
    return ResearchResult(status=status, question=Q, subquestions=(Q,), queries=(Q,), search_health="OK",
                          claims=claims, verified_claims=tuple(c for c in claims if c.status == "SUPPORTED"),
                          conflicts=conflicts, missing_information=("x",), sources=("https://www.sgk.gov.tr/a",))


def test_format_partial_rules():
    main = Claim(text=Q, value=None, period="2026", supporting_evidence_ids=("ev1",), status="SUPPORTED")
    side = Claim(text=Q + " — Resmî Gazete (2026)", value=None, period="2026", supporting_evidence_ids=("ev1",), status="SUPPORTED")
    assert _format_research_result(_result(PARTIAL, (main,))) is not None
    assert _format_research_result(_result(PARTIAL, (side,))) is not None        # resmî-kaynak/Gazete açısı da aynı sorunun kanıtı
    unrelated = Claim(text='Başka konu', value=None, period='2026', supporting_evidence_ids=('ev1',), status='SUPPORTED')
    assert _format_research_result(_result(PARTIAL, (unrelated,))) is None       # soruyla ilgisiz claim sunulmaz
    assert _format_research_result(_result(PARTIAL, ())) is None
    assert _format_research_result(_result(CONFLICTED, (main,), conflicts=(Q,))) is None
    conflicted_partial = _result(PARTIAL, (main,), conflicts=(Q + " — x",))
    assert _format_research_result(conflicted_partial) is None                   # çelişki varken asla sunulmaz


def test_conceptual_accounting_question_gets_labelled_model_answer_when_flag_on_and_refuses_when_off():
    from tests.test_kaizen_brain_research_engine import FakeProvider
    from core.kaizen_brain import KaizenBrain
    from memory.brain_manager import BrainManager
    from memory.learning_store import LearningStore
    root, token = _workspace()
    db = root / f"kb_ar_concept_{token}.sqlite3"
    try:
        for flag, expect_answer in ((True, True), (False, False)):
            store = LearningStore(db)
            class _Seq:
                """1. çağrı (dayanaklı sentez): 'kanıtta yok'; sonraki çağrılar: genel bilgi."""
                def __init__(self):
                    self.n = 0
                def ask(self, prompt):
                    self.n += 1
                    return "Amortisman, maliyetin ait oldukları dönemlere yayılmasıdır."
            brain = KaizenBrain(_Seq(),
                                FakeAccountingAgent(), brain_manager=BrainManager(learning_store=store,
                                experience_memory=NullExperienceMemory(), log_dir=tempfile.mkdtemp()),
                                strict_fact_safety=True, general_accounting_model_answer=flag)
            answer = brain.answer("Amortisman nedir ve nasıl hesaplanır?")
            if expect_answer:
                assert "yayılmasıdır" in answer and answer.startswith("NOT:") and "doğrulanmış" in answer
                assert brain.last_route == "provider" and brain.last_trace.refusal_reason is None
            else:
                assert brain.last_route == "not_found_offline" and "uydurmayacağım" in answer
    finally:
        _cleanup(db)
