"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 18-25 (madde 18-19, 22-25): iddia (Claim) Çıkarma +
Uzlaşı/Çelişki testleri. Sayılar tamamı test uydurmasıdır, gerçek mevzuat değeri değildir
(bkz. tests/test_facts.py'nin aynı disiplini)."""
from research.evidence import build_evidence
from research.extractor import ExtractedContent
from research.models import (
    CONFLICTED,
    INSUFFICIENT,
    PARTIAL,
    ResearchPlan,
    SUPPORTED,
    Subquestion,
)
from research.verifier import build_claims, resolve_topic


def _ev(evidence_id, url, domain, published_at, text, subquestion, requested_period="2026"):
    extracted = ExtractedContent(title="Test", text=text, published_at=published_at, domain=domain)
    return build_evidence(
        evidence_id=evidence_id, subquestion=subquestion, query=subquestion, url=url,
        extracted=extracted, requested_period=requested_period,
    )


def test_resolve_topic_matches_question_terms():
    topic = resolve_topic("2026 fatura düzenleme sınırı ne kadar?")
    assert topic is not None and topic.id == "fatura_duzenleme_siniri"
    assert resolve_topic("bugün hava nasıl olacak") is None
    print("KAIZEN VERIFIER KONU ESLESTIRME (resolve_topic) TESTI: BASARILI")


def test_build_claims_partial_single_official_source_matching_period():
    """YENİ KURAL: Tek resmi kaynak SUPPORTED vermez, single_source (PARTIAL) verir.
    3 kaynak gerekir SUPPORTED (verified) için."""
    subq_text = "2026 SGK prim tavanı nedir"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text, accounting_topic="sgk"),),
        requested_period="2026",
    )
    evidence = _ev(
        "e1", "https://www.sgk.gov.tr/duyuru/2026", "sgk.gov.tr", "2026-01-10",
        "2026 yılı için SGK prim tavanı 750.000 TL'dir.", subq_text,
    )
    claims = build_claims(plan, {subq_text: [evidence]})
    assert len(claims) == 1
    assert claims[0].status == PARTIAL
    assert claims[0].value is None  # single_source -> value None
    assert claims[0].supporting_evidence_ids == ("e1",)
    print("KAIZEN VERIFIER TEK RESMI KAYNAK + DONEM UYUMU -> PARTIAL (single_source) TESTI: BASARILI")


def test_build_claims_conflicted_when_two_independent_sources_disagree():
    subq_text = "2026 fatura düzenleme sınırı ne kadar?"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period="2026",
    )
    ev1 = _ev("e1", "https://www.muhasebetr.com/a", "muhasebetr.com", "2026-02-01",
               "Fatura düzenleme sınırı 2026 yılında 11.111 TL olarak uygulanacaktır.", subq_text)
    ev2 = _ev("e2", "https://www.alomaliye.com/b", "alomaliye.com", "2026-02-05",
               "2026 yılında fatura düzenleme sınırı 12.222 TL oldu.", subq_text)
    claims = build_claims(plan, {subq_text: [ev1, ev2]})
    assert len(claims) == 1
    assert claims[0].status == CONFLICTED
    assert claims[0].value is None
    assert set(claims[0].supporting_evidence_ids) == {"e1", "e2"}
    print("KAIZEN VERIFIER IKI BAGIMSIZ KAYNAK CELISKISI -> CONFLICTED TESTI: BASARILI")


def test_build_claims_partial_when_single_non_official_source():
    subq_text = "2026 fatura düzenleme sınırı ne kadar?"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period="2026",
    )
    ev1 = _ev("e1", "https://www.muhasebetr.com/a", "muhasebetr.com", "2026-02-01",
               "Fatura düzenleme sınırı 2026 yılında 11.111 TL olarak uygulanacaktır.", subq_text)
    claims = build_claims(plan, {subq_text: [ev1]})
    assert len(claims) == 1
    assert claims[0].status == PARTIAL
    assert claims[0].value is None  # madde 13: onaylanmamış sayı Claim.value'ya konmaz
    print("KAIZEN VERIFIER TEK MESLEKI KAYNAK (HENUZ ONAYLANMAMIS) -> PARTIAL TESTI: BASARILI")


def test_build_claims_stale_official_source_downgrades_to_partial():
    """madde 21: resmi kaynak olsa bile istenen donemle uyusmuyorsa SUPPORTED'a
    YUKSELTILMEZ -- 2024 kaynagi 2026 sorusuna 'onaylanmis' cevap SAYILMAZ."""
    subq_text = "2026 SGK prim tavanı nedir"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period="2026",
    )
    stale = _ev(
        "e1", "https://www.sgk.gov.tr/duyuru/2024", "sgk.gov.tr", "2024-01-10",
        "2024 yılı için SGK prim tavanı 400.000 TL'dir.", subq_text, requested_period="2026",
    )
    claims = build_claims(plan, {subq_text: [stale]})
    assert len(claims) == 1
    assert claims[0].status == PARTIAL
    assert claims[0].value is None
    print("KAIZEN VERIFIER ESKI RESMI KAYNAK DONEM UYUSMAZLIGI -> PARTIAL (SUPPORTED DEGIL) TESTI: BASARILI")


def test_build_claims_insufficient_when_source_is_unregistered():
    subq_text = "2026 SGK prim tavanı nedir"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period="2026",
    )
    unknown = _ev(
        "e1", "https://bilinmeyen-site-xyz.com/yazi", "bilinmeyen-site-xyz.com", "2026-01-10",
        "2026 yılı için SGK prim tavanı 500.000 TL'dir.", subq_text,
    )
    claims = build_claims(plan, {subq_text: [unknown]})
    assert len(claims) == 1
    assert claims[0].status == INSUFFICIENT
    assert claims[0].value is None
    assert claims[0].supporting_evidence_ids == ("e1",)
    print("KAIZEN VERIFIER KAYITSIZ (BILINMEYEN) KAYNAK -> INSUFFICIENT TESTI: BASARILI")


def test_build_claims_skips_subquestion_with_no_evidence_at_all():
    """madde 22: hiç kanıt getirilmemiş bir alt-soru icin Claim UYDURULMAZ -- bu durum
    (ResearchResult.missing_information) research/engine.py'nin isidir, burada degil."""
    subq_text = "2026 fatura düzenleme sınırı ne kadar?"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period="2026",
    )
    claims = build_claims(plan, {})
    assert claims == ()
    print("KAIZEN VERIFIER KANITSIZ ALT-SORU ICIN CLAIM UYDURMAZ TESTI: BASARILI")


def test_build_claims_qualitative_supported_via_single_official_source():
    subq_text = "Amortismanın mantığı nedir, faydalı ömür nasıl belirlenir"
    assert resolve_topic(subq_text) is None  # bu bir FactTopic'e eslesmiyor (nitel soru)
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period=None,
    )
    official = _ev(
        "e1", "https://www.gib.gov.tr/rehber/amortisman", "gib.gov.tr", "2026-01-01",
        "Amortisman, bir iktisadi kıymetin ekonomik ömrü boyunca değer kaybını ifade eder. "
        "Amortisman ayrılırken kıymetin faydalı ömrü esas alınır ve amortisman oranı buna göre belirlenir.",
        subq_text, requested_period=None,
    )
    claims = build_claims(plan, {subq_text: [official]})
    assert len(claims) == 1
    assert claims[0].status == SUPPORTED
    assert claims[0].value is None  # nitel iddialarda hicbir zaman sayisal deger yok
    print("KAIZEN VERIFIER NITEL SORU + TEK RESMI KAYNAK -> SUPPORTED TESTI: BASARILI")


def test_build_claims_qualitative_partial_via_single_professional_source():
    subq_text = "Amortismanın mantığı nedir, faydalı ömür nasıl belirlenir"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period=None,
    )
    professional = _ev(
        "e1", "https://www.muhasebetr.com/amortisman-rehberi", "muhasebetr.com", "2026-01-01",
        "Amortisman, bir iktisadi kıymetin ekonomik ömrü boyunca değer kaybını ifade eder. "
        "Amortisman ayrılırken kıymetin faydalı ömrü esas alınır ve amortisman oranı buna göre belirlenir.",
        subq_text, requested_period=None,
    )
    claims = build_claims(plan, {subq_text: [professional]})
    assert len(claims) == 1
    assert claims[0].status == PARTIAL
    print("KAIZEN VERIFIER NITEL SORU + TEK MESLEKI KAYNAK -> PARTIAL TESTI: BASARILI")


def test_build_claims_qualitative_irrelevant_official_source_never_supported():
    """UAT bulgusu (madde 15, RELEASE BLOCKER, 2026-09-24): güvenilir (resmî) bir kaynak
    olmak, o kaynağın PASAJININ SORUYLA İLGİLİ olduğu anlamına GELMEZ. Soru amortisman hakkındayken,
    gib.gov.tr'den TAMAMEN alakasız bir KDV pasajı getirilirse -- eskiden yalnız otorite
    kontrolünden geçtiği için yanlışlıkla SUPPORTED üretiyordu; artık _is_relevant süzgeci
    (Retriever.coverage/phrase_ok) bunu eler ve HİÇ Claim üretilmez."""
    subq_text = "Amortismanın mantığı nedir, faydalı ömür nasıl belirlenir"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period=None,
    )
    irrelevant_official = _ev(
        "e1", "https://www.gib.gov.tr/kdv-genel-tebligi", "gib.gov.tr", "2026-01-01",
        "Genel KDV oranı yüzde 20 olarak uygulanmaktadır. İndirimli oranlar yüzde 1 ve yüzde 10'dur.",
        subq_text, requested_period=None,
    )
    claims = build_claims(plan, {subq_text: [irrelevant_official]})
    assert claims == ()
    print("KAIZEN VERIFIER ALAKASIZ AMA GUVENILIR KAYNAK ASLA SUPPORTED URETMEZ TESTI: BASARILI")


def test_build_claims_qualitative_snippet_only_never_produces_claim():
    """madde 36: snippet-only (hic getirilmemis) kanit tek basina HICBIR Claim'i
    (SUPPORTED dahil) desteklemez -- kanit yoksa iddia da yok."""
    subq_text = "Amortismanın mantığı nedir, faydalı ömür nasıl belirlenir"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period=None,
    )
    snippet_only = build_evidence(
        evidence_id="e1", subquestion=subq_text, query=subq_text,
        url="https://www.gib.gov.tr/rehber/amortisman", extracted=None, requested_period=None,
    )
    claims = build_claims(plan, {subq_text: [snippet_only]})
    assert claims == ()
    print("KAIZEN VERIFIER SNIPPET-ONLY KANIT HICBIR CLAIM URETMEZ TESTI: BASARILI")


def test_build_claims_verified_three_independent_sources_same_value():
    """YENİ KURAL: 3+ bağımsız güvenilir kaynak aynı değeri destekliyorsa VERIFIED (SUPPORTED).
    Value döndürülür."""
    subq_text = "2026 SGK prim tavanı nedir"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text, accounting_topic="sgk"),),
        requested_period="2026",
    )
    # 3 farklı domain: 3 mesleki (muhasebetr.com, muhasebebilenler.com, vergiport.com)
    ev1 = _ev("e1", "https://www.muhasebetr.com/sgk-2026", "muhasebetr.com", "2026-01-15",
               "2026 SGK prim tavanı 750.000 TL olarak belirlendi.", subq_text)
    ev2 = _ev("e2", "https://www.muhasebebilenler.com/prim-tavani", "muhasebebilenler.com", "2026-01-20",
               "Yeni yıl SGK prim tavanı 750.000 TL.", subq_text)
    ev3 = _ev("e3", "https://www.vergiport.com/prim-tavani", "vergiport.com", "2026-01-25",
               "2026 SGK prim tavanı 750.000 TL.", subq_text)
    claims = build_claims(plan, {subq_text: [ev1, ev2, ev3]})
    assert len(claims) == 1
    assert claims[0].status == SUPPORTED  # 3+ kaynak = VERIFIED = SUPPORTED
    assert claims[0].value == "750.000 TL"  # value döndürülür
    assert set(claims[0].supporting_evidence_ids) == {"e1", "e2", "e3"}
    print("KAIZEN VERIFIER 3 BAGIMSIZ KAYNAK AYNI DEGER -> SUPPORTED (VERIFIED) TESTI: BASARILI")


def test_build_claims_single_source_one_professional_source():
    """YENİ KURAL: Tek kaynak (single_source) -> PARTIAL, value=None."""
    subq_text = "2026 fatura düzenleme sınırı ne kadar?"
    plan = ResearchPlan(
        question=subq_text,
        subquestions=(Subquestion(text=subq_text, search_query=subq_text),),
        requested_period="2026",
    )
    ev1 = _ev("e1", "https://www.muhasebetr.com/a", "muhasebetr.com", "2026-02-01",
               "Fatura düzenleme sınırı 2026 yılında 11.111 TL olarak uygulanacaktır.", subq_text)
    claims = build_claims(plan, {subq_text: [ev1]})
    assert len(claims) == 1
    assert claims[0].status == PARTIAL
    assert claims[0].value is None  # single_source -> value None
    print("KAIZEN VERIFIER TEK MESLEKI KAYNAK -> PARTIAL (SINGLE_SOURCE) TESTI: BASARILI")


if __name__ == "__main__":
    test_resolve_topic_matches_question_terms()
    test_build_claims_partial_single_official_source_matching_period()
    test_build_claims_conflicted_when_two_independent_sources_disagree()
    test_build_claims_partial_when_single_non_official_source()
    test_build_claims_stale_official_source_downgrades_to_partial()
    test_build_claims_insufficient_when_source_is_unregistered()
    test_build_claims_skips_subquestion_with_no_evidence_at_all()
    test_build_claims_qualitative_supported_via_single_official_source()
    test_build_claims_qualitative_partial_via_single_professional_source()
    test_build_claims_qualitative_irrelevant_official_source_never_supported()
    test_build_claims_qualitative_snippet_only_never_produces_claim()
    test_build_claims_verified_three_independent_sources_same_value()
    test_build_claims_single_source_one_professional_source()