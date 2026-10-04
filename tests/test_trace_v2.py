"""KAIZEN — KaizenTrace v2 DOĞRULUK testleri: her alan yalnız GERÇEKTEN olan olayı gösterir.

Trace yalnız observability'dir (FACT kaynağı değil); olmayan olay uydurulmaz: Research
çalışmadıysa research_status None kalır, öğrenme denenmediyse reflection_written None kalır."""
import tempfile

from core.trace import KaizenTrace
from search.provider import STATUS_DEGRADED, SearchTimeoutError
from tests.test_kaizen_brain_research_engine import FakeAccountingAgent, _FakeFetcher, _FakeSearchProvider
from tests.test_learning_loop import (
    RESEARCH_Q, _brain, _CorrectingAgent, _RecordingProvider, _supported_search,
)

_V2_FIELDS = (
    "decision", "research_needed", "research_status", "search_provider", "search_health", "query_count",
    "result_count", "fetched_count", "evidence_count", "official_evidence_count", "consensus_status",
    "conflict_count", "principle_candidate", "experience_candidate", "experience_reusable",
    "reflection_written", "user_feedback_effect", "fallback_used", "elapsed_ms",
)


def test_trace_v2_defaults_mean_event_did_not_happen_and_old_fields_are_untouched():
    trace = KaizenTrace()
    for name in _V2_FIELDS:
        assert name in trace.to_dict(), name
    assert trace.research_status is None and trace.search_provider is None
    assert trace.reflection_written is None and trace.experience_candidate is None
    assert trace.fallback_used is False and trace.query_count == 0 and trace.evidence_count == 0
    # v1 alanları ve varsayılanları değişmedi
    assert trace.confidence == "UNKNOWN" and trace.used_research is False and trace.principle_candidates == ()
    print("KAIZEN TRACE V2: VARSAYILAN=OLAY OLMADI, V1 UYUMLU TESTI: BASARILI")


def test_trace_v2_does_not_invent_research_when_engine_is_off_or_route_is_exact():
    with tempfile.TemporaryDirectory() as tmp:
        brain, _ = _brain(tmp, lifecycle=False, advisor=False)     # engine kapalı, öğrenme yok
        brain.answer("125 çarpı 8 kaç eder?")
        t = brain.last_trace
        assert t.decision == "answer_exact" and t.route == "calculator"
        assert t.research_needed is False and t.research_status is None and t.search_provider is None
        assert t.reflection_written is None and isinstance(t.elapsed_ms, int) and t.elapsed_ms >= 0

        # Engine KAPALI + araştırma yolu Hermes: 'research_needed' doğru ama Engine alanları BOŞ
        brain2, _ = _brain(tempfile.mkdtemp(), accounting=_CorrectingAgent(reply="HERMES CEVABI"))
        brain2.answer(RESEARCH_Q)
        t2 = brain2.last_trace
        assert t2.decision == "answer_research_hermes" and t2.research_needed is True
        assert t2.research_status is None and t2.search_provider is None and t2.query_count == 0
        assert t2.fallback_used is False        # Engine hiç denenmedi -> 'fallback' YOK
    print("KAIZEN TRACE V2: OLMAYAN ARASTIRMA/FALLBACK GOSTERILMEZ TESTI: BASARILI")


def test_trace_v2_reflects_real_supported_research_run():
    with tempfile.TemporaryDirectory() as tmp:
        provider, fetcher = _supported_search()
        brain, reflections = _brain(tmp, engine=True, provider=provider, fetcher=fetcher)
        brain.answer(RESEARCH_Q)
        t = brain.last_trace
        assert t.decision == "answer_research_engine" and t.route == "research"
        assert t.research_status == "SUPPORTED" and t.search_provider == "_FakeSearchProvider"
        assert t.search_health == "OK"
        # Sahte sağlayıcı 3 kaynak/alt-soru döndürür (3 resmi kaynak x 4 alt-soru = 12 sonuç)
        assert t.query_count >= 1
        assert t.result_count == t.query_count * 3  # 3 kaynak per query
        assert t.fetched_count == t.evidence_count == t.result_count
        assert 1 <= t.official_evidence_count <= t.evidence_count      # sgk.gov.tr resmî kaynak
        # 3 farklı domain -> 3 bağımsız kaynak
        assert brain._last_research_meta["independent_source_count"] == 3
        assert t.consensus_status == "agreed" and t.conflict_count == 0
        assert t.fallback_used is False and t.reflection_written is True and t.experience_candidate is True
        assert t.confidence == "PENDING"        # araştırma SUPPORTED != VERIFIED: güven etiketi yükselmez
        assert t.needs_current_data is True and t.used_research is True and t.research_needed is True
    print("KAIZEN TRACE V2: GERCEK SUPPORTED ARASTIRMA AKISI TESTI: BASARILI")


def test_trace_v2_reflects_real_search_failure_and_hermes_fallback_honestly():
    with tempfile.TemporaryDirectory() as tmp:
        provider = _FakeSearchProvider(raise_exc=SearchTimeoutError("zaman aşımı"))
        brain, _ = _brain(tmp, engine=True, provider=provider, fetcher=_FakeFetcher({}),
                          accounting=_CorrectingAgent(reply="HERMES YORUMU"))
        brain.answer(RESEARCH_Q)
        t = brain.last_trace
        assert t.research_status == "SEARCH_UNAVAILABLE" and t.search_provider == "_FakeSearchProvider"
        assert t.fallback_used is True and t.decision == "answer_research_hermes"
        assert t.fetched_count == 0 and t.evidence_count == 0 and t.official_evidence_count == 0

        # Hermes de yoksa: dürüst reddetme + gerçek neden cümlesi, rakam uydurma YOK
        provider2 = _FakeSearchProvider(results=(), status=STATUS_DEGRADED)
        brain2, _ = _brain(tempfile.mkdtemp(), engine=True, provider=provider2, fetcher=_FakeFetcher({}),
                           llm=_RecordingProvider("Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod)"),
                           accounting=_CorrectingAgent(reply="Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod)"))
        answer = brain2.answer("Bu yılki KDV oranı yüzde kaç?")   # yerel hafızada kanıt YOK
        assert brain2.last_route == "not_found_offline" and brain2.last_trace.decision == "refuse"
        assert brain2.last_trace.research_status == "SEARCH_DEGRADED" and brain2.last_trace.fallback_used is True
        assert "arama altyapısına" in answer and "cevabı uydurmayacağım" in answer
    print("KAIZEN TRACE V2: ARAMA HATASI + FALLBACK + DURUST RED TESTI: BASARILI")


def test_trace_v2_records_principle_candidate_only_when_retriever_really_ran():
    with tempfile.TemporaryDirectory() as tmp:
        brain, _ = _brain(tmp)
        brain.answer("Stok değerleme yöntemleri nedir?")
        assert brain.last_trace.principle_candidate is None          # Learning Brain kapalı: çalışmadı
        assert brain.last_trace.user_feedback_effect is None
    print("KAIZEN TRACE V2: PRENSIP ADAYI YALNIZ GERCEKTEN CALISTIYSA TESTI: BASARILI")


if __name__ == "__main__":
    test_trace_v2_defaults_mean_event_did_not_happen_and_old_fields_are_untouched()
    test_trace_v2_does_not_invent_research_when_engine_is_off_or_route_is_exact()
    test_trace_v2_reflects_real_supported_research_run()
    test_trace_v2_reflects_real_search_failure_and_hermes_fallback_honestly()
    test_trace_v2_records_principle_candidate_only_when_retriever_really_ran()
