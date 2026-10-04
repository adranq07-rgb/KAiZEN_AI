"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 13 (madde 17-21, 36): Evidence inşası, kaynak
otoritesi ve tazelik/dönem eşleşmesi testleri."""
from research.evidence import (
    build_evidence,
    classify_evidence_passage,
    detect_period,
    source_type_and_authority,
    temporal_matches,
)
from research.extractor import ExtractedContent
from research.models import (
    EVIDENCE_FACT,
    EVIDENCE_HIGH,
    EVIDENCE_HYPOTHETICAL,
    EVIDENCE_LOW,
    EVIDENCE_MEDIUM,
    EVIDENCE_EXAMPLE,
    FETCH_OK,
    FETCH_SNIPPET_ONLY,
    OFFICIAL,
    PROFESSIONAL,
    UNKNOWN_SOURCE,
)


def test_source_type_official_gib_and_sgk():
    t, official, name = source_type_and_authority("https://www.gib.gov.tr/mevzuat")
    assert t == OFFICIAL and official is True and name
    t2, official2, _ = source_type_and_authority("https://www.sgk.gov.tr/duyuru")
    assert t2 == OFFICIAL and official2 is True
    print("KAIZEN RESEARCH EVIDENCE RESMI KAYNAK (GIB/SGK) TESTI: BASARILI")


def test_source_type_professional_and_unknown():
    t, official, name = source_type_and_authority("https://www.muhasebetr.com/makale")
    assert t == PROFESSIONAL and official is False and name
    t2, official2, name2 = source_type_and_authority("https://bilinmeyen-site-xyz.com/yazi")
    assert t2 == UNKNOWN_SOURCE and official2 is False and name2 == ""
    print("KAIZEN RESEARCH EVIDENCE MESLEKI/BILINMEYEN KAYNAK TESTI: BASARILI")


def test_detect_period_prefers_published_at_over_text():
    period = detect_period(published_at="2026-01-05", text="2024 yilinda farkli bir sey oldu")
    assert period == "2026"
    print("KAIZEN RESEARCH EVIDENCE DONEM: PUBLISHED_AT ONCELIGI TESTI: BASARILI")


def test_detect_period_falls_back_to_text_year():
    period = detect_period(published_at=None, text="2026 yilinda asgari ucret guncellendi")
    assert period == "2026"
    print("KAIZEN RESEARCH EVIDENCE DONEM: METINDEN YIL COZUMLEME TESTI: BASARILI")


def test_detect_period_missing_returns_none_not_guessed():
    """madde 20: bulunamazsa UYDURULMAZ."""
    assert detect_period(published_at=None, text="yil bilgisi icermeyen bir metin") is None
    print("KAIZEN RESEARCH EVIDENCE DONEM BULUNAMAZSA UYDURMA YOK TESTI: BASARILI")


def test_temporal_matches_rejects_stale_source_for_current_question():
    """madde 21: 2026 sorusuna 2024 kaynağı -- BAŞARILI eşleşme SAYILMAZ."""
    assert temporal_matches("2026", "2024") is False
    assert temporal_matches("2026", "2026") is True
    assert temporal_matches(None, "2024") is True  # istenen donem bilinmiyorsa reddetmek icin yeterli degil
    print("KAIZEN RESEARCH EVIDENCE ESKI KAYNAK REDDI (DONEM UYUSMAZLIGI) TESTI: BASARILI")


def test_build_evidence_snippet_only_never_high_confidence():
    """madde 13/36: hiç getirilmemiş (yalnız arama sonucu) bir kanıt ASLA yüksek
    güvenle işaretlenemez -- fetch_status=FETCH_SNIPPET_ONLY, confidence=LOW."""
    ev = build_evidence(
        evidence_id="e1", subquestion="2026 SGK tavani", query="sgk tavani 2026",
        url="https://www.sgk.gov.tr/duyuru", extracted=None, requested_period="2026",
    )
    assert ev.fetch_status == FETCH_SNIPPET_ONLY
    assert ev.confidence == EVIDENCE_LOW
    assert ev.has_real_content() is False
    print("KAIZEN RESEARCH EVIDENCE SNIPPET-ONLY ASLA YUKSEK GUVEN DEGIL TESTI: BASARILI")


def test_build_evidence_official_source_matching_period_is_high_confidence():
    extracted = ExtractedContent(
        title="2026 SGK Prim Tavani", text="2026 yilinda SGK prim tavani 195.041,40 TL oldu.",
        published_at="2026-01-10", domain="sgk.gov.tr",
    )
    ev = build_evidence(
        evidence_id="e2", subquestion="2026 SGK prim tavani", query="sgk prim tavani 2026",
        url="https://www.sgk.gov.tr/duyuru/2026", extracted=extracted, requested_period="2026",
    )
    assert ev.fetch_status == FETCH_OK
    assert ev.official is True
    assert ev.period == "2026"
    assert ev.confidence == EVIDENCE_HIGH
    assert "195.041,40" in ev.passage
    print("KAIZEN RESEARCH EVIDENCE RESMI+GUNCEL KAYNAK YUKSEK GUVEN TESTI: BASARILI")


def test_build_evidence_stale_source_downgrades_confidence_even_if_official():
    """madde 21: RESMÎ olsa bile dönem uyuşmuyorsa güven DÜŞÜRÜLÜR -- 'resmî kaynak'
    etiketi tek başına eski bilgiyi güncel gibi göstermeye YETMEZ."""
    extracted = ExtractedContent(
        title="2024 SGK Prim Tavani", text="2024 yilinda SGK prim tavani 150.000 TL idi.",
        published_at="2024-01-10", domain="sgk.gov.tr",
    )
    ev = build_evidence(
        evidence_id="e3", subquestion="2026 SGK prim tavani", query="sgk prim tavani 2026",
        url="https://www.sgk.gov.tr/duyuru/2024", extracted=extracted, requested_period="2026",
    )
    assert ev.official is True  # kaynak yine de resmi
    assert ev.period == "2024"
    assert ev.confidence == EVIDENCE_LOW  # ama GUNCEL DEGIL, guven dusuruldu
    print("KAIZEN RESEARCH EVIDENCE ESKI RESMI KAYNAK GUVEN DUSURME TESTI: BASARILI")


def test_build_evidence_professional_source_matching_period_is_medium_confidence():
    extracted = ExtractedContent(
        title="2026 KDV Oranlari", text="2026 yilinda genel KDV orani yuzde 20 olarak uygulaniyor.",
        published_at="2026-02-01", domain="muhasebetr.com",
    )
    ev = build_evidence(
        evidence_id="e4", subquestion="2026 KDV orani", query="kdv orani 2026",
        url="https://www.muhasebetr.com/makaleler/kdv-2026", extracted=extracted,
        requested_period="2026",
    )
    assert ev.source_type == PROFESSIONAL
    assert ev.confidence == EVIDENCE_MEDIUM
    print("KAIZEN RESEARCH EVIDENCE MESLEKI+GUNCEL KAYNAK ORTA GUVEN TESTI: BASARILI")


def test_build_evidence_missing_date_kept_as_none_not_guessed():
    extracted = ExtractedContent(
        title="Genel Bilgi", text="Amortisman faydali omur boyunca uygulanir.",
        published_at="", domain="ozdogrular.com",
    )
    ev = build_evidence(
        evidence_id="e5", subquestion="amortisman mantigi", query="amortisman",
        url="https://www.ozdogrular.com/yazi/amortisman", extracted=extracted,
        requested_period=None,
    )
    assert ev.published_at is None
    assert ev.period is None
    print("KAIZEN RESEARCH EVIDENCE EKSIK TARIH UYDURULMAZ TESTI: BASARILI")


def test_musavirler_kulubu_is_professional_source():
    """madde 13: Müşavirler Kulübü güvenilir profesyonel kaynak olarak kaydedilmeli."""
    t, official, name = source_type_and_authority("https://www.musavirlerkulubu.com.tr/makale")
    assert t == PROFESSIONAL and official is False and name == "Muhasebe Bilenler"
    print("KAIZEN MUSAVIRLER KULUBU PROFESYONEL KAYNAK TESTI: BASARILI")


def test_evidence_classification_hypothetical_vs_factual():
    """madde 15: hypothetical passage'lar consensus dışı olmalı, factual ise FACT."""
    # Hypothetical: 24.000 TL varsayımsal
    hypothetical_passage = "2026 yılı için varsayımsal brüt asgari ücret 24.000 TL olarak belirlenmiştir."
    result = classify_evidence_passage(hypothetical_passage)
    assert result == EVIDENCE_HYPOTHETICAL
    
    # Factual: 33.030 TL doğru
    factual_passage = "2026 yılı için geçerli brüt asgari ücret 33.030,00 TL olarak belirlenmiştir."
    result2 = classify_evidence_passage(factual_passage)
    assert result2 == EVIDENCE_FACT
    
    # Example passage
    # "örnek" kelimesi nedeniyle HYPOTHETICAL olarak işaretlenir
    # (negatif sinyal listesinde "örnek" olduğu için)
    example_passage = "örnek hesaplama için 24.000 TL kabul edelim"
    result3 = classify_evidence_passage(example_passage)
    assert result3 in (EVIDENCE_HYPOTHETICAL, EVIDENCE_EXAMPLE)  # Her iki sınıflama da kabul edilebilir
    
    print("KAIZEN EVIDENCE CLASSIFICATION HYPOTHETICAL VS FACT TESTI: BASARILI")


if __name__ == "__main__":
    test_source_type_official_gib_and_sgk()
    test_source_type_professional_and_unknown()
    test_detect_period_prefers_published_at_over_text()
    test_detect_period_falls_back_to_text_year()
    test_detect_period_missing_returns_none_not_guessed()
    test_temporal_matches_rejects_stale_source_for_current_question()
    test_build_evidence_snippet_only_never_high_confidence()
    test_build_evidence_official_source_matching_period_is_high_confidence()
    test_build_evidence_stale_source_downgrades_confidence_even_if_official()
    test_build_evidence_professional_source_matching_period_is_medium_confidence()
    test_build_evidence_missing_date_kept_as_none_not_guessed()
