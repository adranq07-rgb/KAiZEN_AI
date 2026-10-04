"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 7-8 (madde 8/17/26-27): `research/models.py`
sözleşmelerinin kendi kendine tutarlılık testleri. Bu dosya HENÜZ hiçbir ağ/arama
çağrısı yapmaz -- yalnız dataclass invariant'larını doğrular."""
from research.models import (
    Claim,
    Evidence,
    OFFICIAL,
    PROFESSIONAL,
    ResearchModelError,
    ResearchPlan,
    ResearchResult,
    SUPPORTED,
    Subquestion,
    UNKNOWN_SOURCE,
    FETCH_OK,
    FETCH_SNIPPET_ONLY,
)


def _evidence(**overrides):
    base = dict(
        evidence_id="e1", query="q", subquestion="sq", url="https://gib.gov.tr/x",
        domain="gib.gov.tr", source_name="Gelir Idaresi Baskanligi", source_type=OFFICIAL,
        title="t", published_at="2026-01-01", retrieved_at="2026-09-24T00:00:00",
        passage="pasaj", extracted_claim="iddia", official=True, fetch_status=FETCH_OK,
    )
    base.update(overrides)
    return Evidence(**base)


def test_subquestion_rejects_empty_fields():
    Subquestion(text="soru", search_query="sorgu")
    for bad in (dict(text="", search_query="x"), dict(text="x", search_query="")):
        try:
            Subquestion(**bad)
            assert False, "boş alan kabul edilmemeli"
        except ResearchModelError:
            pass
    print("KAIZEN RESEARCH MODELS SUBQUESTION BOS ALAN REDDI TESTI: BASARILI")


def test_research_plan_requires_at_least_one_subquestion():
    try:
        ResearchPlan(question="soru", subquestions=())
        assert False
    except ResearchModelError:
        pass
    plan = ResearchPlan(question="soru", subquestions=(Subquestion("a", "b"),))
    assert len(plan.subquestions) == 1
    print("KAIZEN RESEARCH MODELS PLAN EN AZ 1 ALT SORU TESTI: BASARILI")


def test_evidence_rejects_invalid_source_type_and_confidence():
    try:
        _evidence(source_type="RESMI")  # gecersiz sabit
        assert False
    except ResearchModelError:
        pass
    try:
        _evidence(confidence="COK_YUKSEK")
        assert False
    except ResearchModelError:
        pass
    print("KAIZEN RESEARCH MODELS EVIDENCE GECERSIZ SABIT REDDI TESTI: BASARILI")


def test_evidence_official_flag_must_match_source_type():
    try:
        _evidence(source_type=PROFESSIONAL, official=True)
        assert False, "official=True ama source_type PROFESSIONAL olmamalı"
    except ResearchModelError:
        pass
    print("KAIZEN RESEARCH MODELS EVIDENCE OFFICIAL/SOURCE_TYPE TUTARLILIGI TESTI: BASARILI")


def test_evidence_has_real_content_distinguishes_snippet_only():
    fetched = _evidence(fetch_status=FETCH_OK)
    snippet = _evidence(evidence_id="e2", fetch_status=FETCH_SNIPPET_ONLY, official=False,
                         source_type=UNKNOWN_SOURCE)
    assert fetched.has_real_content() is True
    assert snippet.has_real_content() is False
    print("KAIZEN RESEARCH MODELS SNIPPET-ONLY AYRIMI TESTI: BASARILI")


def test_claim_requires_at_least_one_evidence_id_and_valid_status():
    try:
        Claim(text="iddia", value="25", period="2026", supporting_evidence_ids=(), status=SUPPORTED)
        assert False, "kaynaksız claim kabul edilmemeli"
    except ResearchModelError:
        pass
    try:
        Claim(text="iddia", value="25", period="2026", supporting_evidence_ids=("e1",),
              status="VERIFIED")
        assert False, "Claim.status asla VERIFIED olamaz"
    except ResearchModelError:
        pass
    ok = Claim(text="iddia", value="25", period="2026", supporting_evidence_ids=("e1",),
               status=SUPPORTED)
    assert ok.status == SUPPORTED
    print("KAIZEN RESEARCH MODELS CLAIM KAYNAK/DURUM SOZLESMESI TESTI: BASARILI")


def test_research_result_verified_claims_must_be_subset_of_claims():
    ev = _evidence()
    c1 = Claim(text="a", value="1", period="2026", supporting_evidence_ids=(ev.evidence_id,),
               status=SUPPORTED)
    c2 = Claim(text="b", value="2", period="2026", supporting_evidence_ids=(ev.evidence_id,),
               status=SUPPORTED)
    try:
        ResearchResult(
            status=SUPPORTED, question="q", subquestions=("sq",), queries=("q",),
            search_health="OK", evidence=(ev,), claims=(c1,), verified_claims=(c2,),
        )
        assert False, "verified_claims, claims disinda bir claim icermemeli"
    except ResearchModelError:
        pass
    ok = ResearchResult(
        status=SUPPORTED, question="q", subquestions=("sq",), queries=("q",),
        search_health="OK", evidence=(ev,), claims=(c1,), verified_claims=(c1,),
    )
    assert ok.verified_claims == (c1,)
    print("KAIZEN RESEARCH MODELS VERIFIED_CLAIMS ALT KUME TESTI: BASARILI")


def test_research_result_rejects_snippet_only_verified_claim():
    """madde 36: snippet-only bir sonuç ASLA VERIFIED/SUPPORTED bir claim'in TEK
    dayanağı olamaz."""
    snippet_ev = _evidence(evidence_id="e_snippet", fetch_status=FETCH_SNIPPET_ONLY)
    claim = Claim(text="iddia", value="25", period="2026",
                  supporting_evidence_ids=("e_snippet",), status=SUPPORTED)
    try:
        ResearchResult(
            status=SUPPORTED, question="q", subquestions=("sq",), queries=("q",),
            search_health="OK", evidence=(snippet_ev,), claims=(claim,),
            verified_claims=(claim,),
        )
        assert False, "yalnizca snippet-only kanitla desteklenen claim VERIFIED/SUPPORTED olmamali"
    except ResearchModelError:
        pass
    print("KAIZEN RESEARCH MODELS SNIPPET-ONLY ASLA VERIFIED DEGIL TESTI: BASARILI")


def test_research_result_status_must_be_in_contract():
    try:
        ResearchResult(status="VERIFIED", question="q", subquestions=(), queries=(),
                       search_health="OK")
        assert False
    except ResearchModelError:
        pass
    print("KAIZEN RESEARCH MODELS RESULT STATUS SOZLESMESI TESTI: BASARILI")


if __name__ == "__main__":
    test_subquestion_rejects_empty_fields()
    test_research_plan_requires_at_least_one_subquestion()
    test_evidence_rejects_invalid_source_type_and_confidence()
    test_evidence_official_flag_must_match_source_type()
    test_evidence_has_real_content_distinguishes_snippet_only()
    test_claim_requires_at_least_one_evidence_id_and_valid_status()
    test_research_result_verified_claims_must_be_subset_of_claims()
    test_research_result_rejects_snippet_only_verified_claim()
    test_research_result_status_must_be_in_contract()
