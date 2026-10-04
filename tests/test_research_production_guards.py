"""KAIZEN — Research Engine ÜRETİM AKTİVASYONU guard'ları.

UAT PASS sonrası `research.research_engine_enabled` açılmadan ÖNCE kodda gerçekten var olması
gereken güvenlik kapıları, tek tek DAVRANIŞLA doğrulanır (kod okuma değil, çalıştırma):
  provider unavailable -> güvenli fallback | SEARCH_DEGRADED -> hallucination yok |
  PARTIAL/INSUFFICIENT/CONFLICTED -> verified gibi sunulmaz | SUPPORTED + verified_claims şartı |
  exception -> eski davranış | deterministik/fact önceliği | SafeFetcher aktif | kaynak/kanıt trace.
Ayrıca 'SUPPORTED != FactRegistry VERIFIED' sınırı: research sonucu parametre defterine YAZILMAZ."""
import json
import tempfile
from pathlib import Path

from accounting.facts import FactRegistry
from core.engine import KaizenEngine
from core.ai.offline_provider import OfflineProvider
from core.kaizen_brain import _format_research_result
from research.fetcher import SafeFetcher
from research.models import (
    CONFLICTED, INSUFFICIENT, PARTIAL, ResearchResult, SEARCH_DEGRADED, SEARCH_UNAVAILABLE, SUPPORTED,
)
from search.provider import STATUS_DEGRADED, SearchTimeoutError
from tests.test_kaizen_brain_research_engine import _FakeFetcher, _FakeSearchProvider, _sr
from tests.test_learning_loop import (
    RESEARCH_Q, _brain, _CorrectingAgent, _RecordingProvider, _supported_search,
)

_OFFLINE = "Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod)"
_ROOT = Path(__file__).resolve().parent.parent


def test_guard_provider_unavailable_and_degraded_fall_back_safely_without_hallucination():
    for provider in (
        _FakeSearchProvider(raise_exc=SearchTimeoutError("arama yok")),          # SEARCH_UNAVAILABLE
        _FakeSearchProvider(results=(), status=STATUS_DEGRADED),                  # SEARCH_DEGRADED
        _FakeSearchProvider(raise_exc=RuntimeError("beklenmeyen")),               # exception
    ):
        with tempfile.TemporaryDirectory() as tmp:
            brain, _ = _brain(tmp, engine=True, provider=provider, fetcher=_FakeFetcher({}),
                              llm=_RecordingProvider(_OFFLINE), accounting=_CorrectingAgent(reply=_OFFLINE))
            answer = brain.answer("Bu yılki KDV oranı yüzde kaç?")
            assert brain.last_route == "not_found_offline"                       # uydurma cevap YOK
            assert "cevabı uydurmayacağım" in answer and not any(ch.isdigit() for ch in answer)
            assert brain.last_trace.confidence == "UNKNOWN"
    print("KAIZEN RESEARCH GUARD: SAGLAYICI YOK/DEGRADED/EXCEPTION -> GUVENLI FALLBACK TESTI: BASARILI")


def test_guard_only_supported_with_verified_claims_is_presented_and_never_as_verified():
    for status in (PARTIAL, INSUFFICIENT, CONFLICTED, SEARCH_DEGRADED, SEARCH_UNAVAILABLE):
        result = ResearchResult(status=status, question="q", subquestions=("a",), queries=("a",), search_health="OK")
        assert _format_research_result(result) is None, status
    # SUPPORTED ama hiç verified_claim yok -> sunulmaz
    empty = ResearchResult(status=SUPPORTED, question="q", subquestions=("a",), queries=("a",), search_health="OK")
    assert _format_research_result(empty) is None
    # Gerçek SUPPORTED akışı: metin 'VERIFIED' demez, güven etiketi PENDING kalır, kaynak gösterilir
    with tempfile.TemporaryDirectory() as tmp:
        provider, fetcher = _supported_search()
        brain, _ = _brain(tmp, engine=True, provider=provider, fetcher=fetcher)
        answer = brain.answer(RESEARCH_Q)
        assert "VERIFIED" not in answer and "KAYNAKLAR:" in answer and "sgk.gov.tr" in answer
        assert brain.last_trace.confidence == "PENDING" and brain.last_trace.evidence_count >= 1
    print("KAIZEN RESEARCH GUARD: SUPPORTED+VERIFIED_CLAIMS SARTI, VERIFIED GIBI SUNULMAZ TESTI: BASARILI")


def test_guard_research_supported_never_writes_to_fact_registry():
    with tempfile.TemporaryDirectory() as tmp:
        provider, fetcher = _supported_search()
        registry = FactRegistry(Path(tmp) / "facts.sqlite3")
        brain, _ = _brain(tmp, engine=True, provider=provider, fetcher=fetcher, facts=registry)
        assert brain.brain.facts is registry
        facts_before = registry.rows()
        brain.answer(RESEARCH_Q)
        # 'facts' rotası araştırma cevabından SONRA da bu soruyu VERIFIED yapmaz
        brain.answer(RESEARCH_Q)
        assert brain.last_route != "facts" and brain.last_trace.confidence != "VERIFIED"
        assert registry.rows() == facts_before        # parametre defterine HİÇBİR satır yazılmadı
    print("KAIZEN RESEARCH GUARD: SUPPORTED != FACTREGISTRY VERIFIED SINIRI TESTI: BASARILI")


def test_guard_deterministic_and_fact_layers_run_before_research():
    with tempfile.TemporaryDirectory() as tmp:
        provider, fetcher = _supported_search()
        brain, _ = _brain(tmp, engine=True, provider=provider, fetcher=fetcher)
        brain.answer("125 çarpı 8 kaç eder?")
        brain.answer("15 Ocak 2026 ile 20 Mart 2026 arasında kaç gün var?")   # yıl içeriyor ama HESAPLANABİLİR
        assert provider.calls == 0 and brain.last_route == "calculator"
    print("KAIZEN RESEARCH GUARD: DETERMINISTIK ONCELIK KORUNUYOR TESTI: BASARILI")


def test_guard_default_fetcher_blocks_internal_urls():
    """Fetcher (SafeFetcher veya ScraplingAdapter) SSRF koruması sağlar: localhost/private IP engellenir."""
    with tempfile.TemporaryDirectory() as tmp:
        url = "http://127.0.0.1:9/gizli"      # SSRF: iç ağ adresi -- fetcher engellemeli, bağlantı KURULMAMALI
        provider = _FakeSearchProvider(results=[_sr(url, RESEARCH_Q)])
        brain, _ = _brain(tmp, engine=True, provider=provider, fetcher=None,
                          accounting=_CorrectingAgent(reply="HERMES YORUMU"))
        brain.answer(RESEARCH_Q)
        # Fetcher SSRF koruması sağladığı için fetch_count == 0 olmalı
        assert brain.last_trace.fetched_count == 0 and brain.last_trace.evidence_count == 0
        assert brain.last_trace.research_status not in (None, "SUPPORTED") and brain.last_trace.fallback_used is True
    print("KAIZEN RESEARCH GUARD: FETCHER SSRF KORUMASI + IC AG ENGELI TESTI: BASARILI")


def test_guard_production_config_activates_research_and_engine_wires_the_learning_loop():
    config = json.loads((_ROOT / "config" / "Kaizen.json").read_text(encoding="utf-8"))
    assert config["research"]["research_engine_enabled"] is True                 # aktivasyon (guard'lar yukarıda kanıtlı)
    assert config["learning"]["experience_lifecycle_enabled"] is True
    with tempfile.TemporaryDirectory() as tmp:
        engine = KaizenEngine(data_dir=Path(tmp) / "data", log_dir=Path(tmp) / "logs", provider=OfflineProvider())
        assert engine.brain.research_engine_enabled is True and engine.search_provider is not None
        assert engine.brain._reflection_lifecycle is not None and engine.brain._strategy_advisor is not None
        # Hermes KALDIRILMADI: fallback/yorumlayıcı olarak zincirde duruyor
        assert engine.accounting_agent is not None and engine.brain.accounting_agent is engine.accounting_agent
        # Reflection deposu GEÇİCİ data_dir'de (gerçek data/ değil)
        assert str(engine.reflection_store.db_path).startswith(tmp)
    print("KAIZEN RESEARCH GUARD: URETIM AKTIVASYONU + LEARNING LOOP BAGLANTISI TESTI: BASARILI")


if __name__ == "__main__":
    test_guard_provider_unavailable_and_degraded_fall_back_safely_without_hallucination()
    test_guard_only_supported_with_verified_claims_is_presented_and_never_as_verified()
    test_guard_research_supported_never_writes_to_fact_registry()
    test_guard_deterministic_and_fact_layers_run_before_research()
    test_guard_default_fetcher_blocks_internal_urls()
    test_guard_production_config_activates_research_and_engine_wires_the_learning_loop()
