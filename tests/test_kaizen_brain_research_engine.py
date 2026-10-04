"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 28-31 (madde 28-31): Research Engine'in `KaizenBrain`'e
DAR entegrasyonunun testleri. Kural (madde 30, kritik): `research_engine_enabled=False`
(varsayılan) VEYA `search_provider=None` iken davranış BİREBİR eskisi gibi kalmalı (doğrudan
Hermes); bayrak açık olsa bile Research Engine yalnız SUPPORTED bir sonuç bulursa Hermes'in
YERİNİ alır, aksi halde (PARTIAL/INSUFFICIENT/arama hatası/beklenmeyen exception dahil)
Hermes HİÇ ETKİLENMEDEN fallback olarak çalışmaya devam eder. GERÇEK AĞ YOK -- test double'lar
(bkz. tests/test_research_engine.py ile AYNI disiplin)."""
import tempfile
from pathlib import Path
from uuid import uuid4

from core.kaizen_brain import KaizenBrain, _format_research_result
from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore
from research.fetcher import FetchOutcome
from research.models import (
    CONFLICTED,
    INSUFFICIENT,
    PARTIAL,
    ResearchResult,
    SEARCH_UNAVAILABLE,
)
from search.provider import SearchOutcome, SearchResult, STATUS_EMPTY, STATUS_OK
from tests.doubles import NullExperienceMemory


def _workspace():
    root = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root, uuid4().hex


def _cleanup(*paths):
    for db in paths:
        for suffix in ("", "-shm", "-wal"):
            Path(str(db) + suffix).unlink(missing_ok=True)


class FakeProvider:
    def __init__(self, reply="YEREL BİLGİDEN CEVAP"):
        self.reply = reply

    def ask(self, prompt):
        return self.reply


class FakeAccountingAgent:
    def __init__(self, reply="GÜNCEL ARAŞTIRMA (HERMES)"):
        self.reply = reply
        self.calls = 0
        self.question = None

    def ask(self, question):
        self.calls += 1
        self.question = question
        return self.reply


class _FakeSearchProvider:
    def __init__(self, results=(), status=STATUS_OK, raise_exc=None):
        self.results = results
        self.status = status
        self.raise_exc = raise_exc
        self.calls = 0

    def search(self, query, options=None):
        self.calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc
        return SearchOutcome(results=tuple(self.results), query=query, status=self.status)


class _FakeFetcher:
    def __init__(self, outcomes_by_url):
        self.outcomes_by_url = outcomes_by_url

    def fetch(self, url):
        return self.outcomes_by_url.get(url, FetchOutcome(status="FETCH_BLOCKED_ROBOTS", url=url, final_url=url))


def _sr(url, query):
    return SearchResult(
        title="Test", url=url, snippet="...", engine="fake", engines=("fake",), category="general",
        score=1.0, published_date=None, domain=url.split("/")[2], is_pdf=False, query=query,
    )


def _html(sentence):
    return (
        f"<html><head><title>Test</title>"
        f"<meta property=\"article:published_time\" content=\"2026-01-05T10:00:00+03:00\"></head>"
        f"<body><article><p>{sentence}</p></article></body></html>"
    ).encode("utf-8")


def _brain(db, accounting, research_engine_enabled=False, search_provider=None, research_fetcher=None,
           strict_fact_safety=False):
    store = LearningStore(db)
    return KaizenBrain(
        FakeProvider(), accounting,
        brain_manager=BrainManager(
            learning_store=store, experience_memory=NullExperienceMemory(), log_dir=tempfile.mkdtemp(),
        ),
        research_engine_enabled=research_engine_enabled, search_provider=search_provider,
        research_fetcher=research_fetcher,
        strict_fact_safety=strict_fact_safety,
    )


def test_research_engine_disabled_by_default_uses_hermes_unchanged():
    """madde 30 (KIRMIZI ÇİZGİ): varsayılan (flag kapalı, provider yok) davranış BİREBİR
    eskisi gibi -- doğrudan Hermes."""
    root, token = _workspace()
    db = root / f"kb_re_off_{token}.sqlite3"
    try:
        accounting = FakeAccountingAgent()
        brain = _brain(db, accounting)
        answer = brain.answer("2026 SGK prim tavanı nedir?")
        assert answer == "GÜNCEL ARAŞTIRMA (HERMES)"
        assert accounting.calls == 1
        assert brain._last_research_via == "hermes"
    finally:
        _cleanup(db)
    print("KAIZEN BEYIN + RESEARCH ENGINE: VARSAYILAN KAPALI -> HERMES BIREBIR TESTI: BASARILI")


def test_research_engine_enabled_but_no_provider_falls_back_safely():
    """madde 28: bayrak açık ama search_provider hiç verilmemiş (yanlış yapılandırma) --
    ÇÖKMEZ, sessizce Hermes'e düşer."""
    root, token = _workspace()
    db = root / f"kb_re_noprovider_{token}.sqlite3"
    try:
        accounting = FakeAccountingAgent()
        brain = _brain(db, accounting, research_engine_enabled=True, search_provider=None)
        answer = brain.answer("2026 SGK prim tavanı nedir?")
        assert answer == "GÜNCEL ARAŞTIRMA (HERMES)"
        assert accounting.calls == 1
    finally:
        _cleanup(db)
    print("KAIZEN BEYIN + RESEARCH ENGINE: SAGLAYICI YOKKEN GUVENLE HERMES'E DUSER TESTI: BASARILI")


def test_research_engine_supported_result_replaces_hermes_call():
    """madde 27-28: Research Engine SUPPORTED (3+ bağımsız kaynak, dönem uyumlu) bir sonuç
    bulursa, Hermes HİÇ ÇAĞRILMAZ -- Research Engine'in metni doğrudan döner."""
    root, token = _workspace()
    db = root / f"kb_re_supported_{token}.sqlite3"
    try:
        question = "2026 SGK prim tavanı nedir?"
        urls = (
            "https://www.sgk.gov.tr/duyuru/2026",
            "https://www.resmigazete.gov.tr/sgk-2026",
            "https://www.mevzuat.gov.tr/sgk-prim-2026",
        )
        provider = _FakeSearchProvider(results=[_sr(u, question) for u in urls])
        fetcher = _FakeFetcher({
            urls[0]: FetchOutcome(
                status="FETCH_OK", url=urls[0], final_url=urls[0], content_type="text/html; charset=utf-8",
                body=_html("2026 yılı için SGK prim tavanı 750.000 TL'dir."),
            ),
            urls[1]: FetchOutcome(
                status="FETCH_OK", url=urls[1], final_url=urls[1], content_type="text/html; charset=utf-8",
                body=_html("Resmi Gazete: 2026 SGK prim tavanı 750.000 TL olarak ilan edildi."),
            ),
            urls[2]: FetchOutcome(
                status="FETCH_OK", url=urls[2], final_url=urls[2], content_type="text/html; charset=utf-8",
                body=_html("Mevzuat: SGK prim tavanı 2026 için 750.000 TL'dir."),
            ),
        })
        accounting = FakeAccountingAgent()
        brain = _brain(
            db, accounting, research_engine_enabled=True, search_provider=provider, research_fetcher=fetcher,
        )
        answer = brain.answer(question)
        assert accounting.calls == 0  # Hermes'e HIC gidilmedi
        assert answer.startswith("SONUÇ:") and "750.000 TL" in answer
        assert "VERIFIED" not in answer  # madde 13: bu etiket asla kullanilmaz
        assert brain._last_research_via == "engine"
    finally:
        _cleanup(db)
    print("KAIZEN BEYIN + RESEARCH ENGINE: SUPPORTED SONUC HERMES'IN YERINI ALIR TESTI: BASARILI")


def test_research_engine_insufficient_result_still_falls_back_to_hermes():
    """madde 30: Research Engine PARTIAL/INSUFFICIENT/arama-basarisiz dönerse -- yani
    SUPPORTED DEĞİLSE -- Hermes yine HER ZAMANKİ GİBİ çağrılır, hiçbir şey gizlenmez."""
    root, token = _workspace()
    db = root / f"kb_re_insufficient_{token}.sqlite3"
    try:
        question = "2026 SGK prim tavanı nedir?"
        provider = _FakeSearchProvider(results=(), status=STATUS_EMPTY)
        fetcher = _FakeFetcher({})
        accounting = FakeAccountingAgent()
        brain = _brain(
            db, accounting, research_engine_enabled=True, search_provider=provider, research_fetcher=fetcher,
        )
        answer = brain.answer(question)
        assert accounting.calls == 1  # Hermes fallback CALISTI
        assert answer == "GÜNCEL ARAŞTIRMA (HERMES)"
        assert brain._last_research_via == "hermes"
    finally:
        _cleanup(db)
    print("KAIZEN BEYIN + RESEARCH ENGINE: YETERSIZ SONUC HERMES FALLBACK'E DUSER TESTI: BASARILI")


def test_research_engine_unexpected_exception_never_crashes_answer():
    """madde 26: SearchProvider'da BEKLENMEYEN (SearchProviderError DIŞINDA) bir hata
    olsa bile brain.answer() ASLA çökmez -- savunma katmanı (_research_engine_once'daki
    genis try/except) devreye girer, Hermes'e guvenle duser."""
    root, token = _workspace()
    db = root / f"kb_re_crash_{token}.sqlite3"
    try:
        question = "2026 SGK prim tavanı nedir?"
        provider = _FakeSearchProvider(raise_exc=RuntimeError("beklenmeyen hata"))
        fetcher = _FakeFetcher({})
        accounting = FakeAccountingAgent()
        brain = _brain(
            db, accounting, research_engine_enabled=True, search_provider=provider, research_fetcher=fetcher,
        )
        answer = brain.answer(question)  # ASLA raise ETMEMELI
        assert accounting.calls == 1
        assert answer == "GÜNCEL ARAŞTIRMA (HERMES)"
    finally:
        _cleanup(db)
    print("KAIZEN BEYIN + RESEARCH ENGINE: BEKLENMEYEN HATADA COKMEZ, HERMES'E DUSER TESTI: BASARILI")


def test_format_research_result_only_accepts_supported_with_verified_claims():
    """`_format_research_result` doğrudan birim testi: yalnız SUPPORTED + en az bir
    verified_claim varsa metin döner, aksi HER durumda None -- madde 13/27."""
    base = dict(
        question="q", subquestions=("q",), queries=("q",), search_health=STATUS_OK, evidence=(),
    )
    for status in (PARTIAL, CONFLICTED, INSUFFICIENT, SEARCH_UNAVAILABLE):
        result = ResearchResult(status=status, claims=(), verified_claims=(), **base)
        assert _format_research_result(result) is None
    print("KAIZEN _FORMAT_RESEARCH_RESULT: YALNIZ SUPPORTED+VERIFIED_CLAIMS TESTI: BASARILI")


def test_current_accounting_question_reaches_research_engine():
    """Routing fix: current accounting sorusu Research Engine'e ulaşmalı.
    Bu, daha önce `domain == "general"` koşulu nedeniyle TÜM muhasebe sorularının
    Research Engine'e ulaşmadan `not_found_offline` döndüğü bug'ın kalıcı regression testidir."""
    root, token = _workspace()
    db = root / f"kb_re_current_acc_{token}.sqlite3"
    try:
        question = "2026 SGK prim tavanı nedir?"
        url = "https://www.sgk.gov.tr/duyuru/2026"
        provider = _FakeSearchProvider(results=[_sr(url, question)])
        fetcher = _FakeFetcher({
            url: FetchOutcome(
                status="FETCH_OK", url=url, final_url=url, content_type="text/html; charset=utf-8",
                body=_html("2026 yılı için SGK prim tavanı 500.000 TL'dir."),
            ),
        })
        accounting = FakeAccountingAgent()
        brain = _brain(
            db, accounting,
            research_engine_enabled=True,
            search_provider=provider,
            research_fetcher=fetcher,
            strict_fact_safety=True,
        )
        answer = brain.answer(question)
        assert brain.last_trace.used_research, "current accounting sorusu Research Engine'e ulaşmalı"
        assert brain.last_trace.research_status is not None, "research_status dolu olmalı"
    finally:
        _cleanup(db)
    print("KAIZEN RESEARCH ROUTING: CURRENT ACCOUNTING -> RESEARCH ENGINE TESTI: BASARILI")


def test_non_current_accounting_question_skips_research_engine():
    """Routing fix: non-current accounting sorusu gereksiz research yapmamalı."""
    root, token = _workspace()
    db = root / f"kb_re_noncurrent_acc_{token}.sqlite3"
    try:
        question = "Mizan nedir?"
        provider = _FakeSearchProvider(results=[])
        accounting = FakeAccountingAgent()
        brain = _brain(
            db, accounting,
            research_engine_enabled=True,
            search_provider=provider,
            strict_fact_safety=True,
        )
        brain.answer(question)
        assert not brain.last_trace.used_research, "non-current sorusu research yapmamalı"
        assert provider.calls == 0, "SearchProvider hic cagrilmamali"
    finally:
        _cleanup(db)
    print("KAIZEN RESEARCH ROUTING: NON-CURRENT ACCOUNTING -> RESEARCH YOK TESTI: BASARILI")


def test_research_partial_strict_fact_safety_no_fabricated_answer():
    """Routing fix: Research Engine PARTIAL döndüğünde strict fact safety
    uydurma factual answer üretmemeli."""
    root, token = _workspace()
    db = root / f"kb_re_partial_strict_{token}.sqlite3"
    try:
        question = "2026 SGK prim tavanı nedir?"
        provider = _FakeSearchProvider(results=(), status=STATUS_EMPTY)
        fetcher = _FakeFetcher({})
        accounting = FakeAccountingAgent()
        brain = _brain(
            db, accounting,
            research_engine_enabled=True,
            search_provider=provider,
            research_fetcher=fetcher,
            strict_fact_safety=True,
        )
        answer = brain.answer(question)
        assert brain.last_route == "not_found_offline"
        assert brain.last_trace.used_research
        assert "uydurmayacağım" in answer
        assert "500.000" not in answer and "TL" not in answer.split("uydurmayacağım")[0][-50:]
    finally:
        _cleanup(db)
    print("KAIZEN RESEARCH ROUTING: PARTIAL + STRICT FACT SAFETY -> UYDURMA YOK TESTI: BASARILI")


if __name__ == "__main__":
    test_research_engine_disabled_by_default_uses_hermes_unchanged()
    test_research_engine_enabled_but_no_provider_falls_back_safely()
    test_research_engine_supported_result_replaces_hermes_call()
    test_research_engine_insufficient_result_still_falls_back_to_hermes()
    test_research_engine_unexpected_exception_never_crashes_answer()
    test_format_research_result_only_accepts_supported_with_verified_claims()
    test_current_accounting_question_reaches_research_engine()
    test_non_current_accounting_question_skips_research_engine()
    test_research_partial_strict_fact_safety_no_fabricated_answer()
