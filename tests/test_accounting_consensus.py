from accounting.consensus import AccountingConsensus, FactCandidate


def test_accounting_consensus():
    decide = AccountingConsensus().decide
    old = FactCandidate("fatura siniri", "6900", 2025,
                        "https://www.muhasebetr.com/eski", "2025 siniri 6900")
    new_a = FactCandidate("fatura siniri", "9900", 2026,
                          "https://www.muhasebetr.com/yeni", "2026 siniri 9900")
    # 1 source -> single_source (eski: pending_confirmation)
    assert decide([old, new_a]).status == "single_source"

    new_b = FactCandidate("fatura siniri", "9.900", 2026,
                          "https://www.alomaliye.com/makaleler/yeni", "2026 siniri 9.900")
    # 2 sources -> partially_verified (eski: verified)
    result = decide([old, new_a, new_b])
    assert result.status == "partially_verified"
    assert result.effective_year == 2026

    # Official source alone -> single_source (eski: verified)
    official = FactCandidate("kurumlar vergisi", "%25", 2026,
                             "https://www.gib.gov.tr/oran", "Genel oran %25")
    assert decide([official]).status == "single_source"

    # 3+ sources -> verified
    third = FactCandidate("fatura siniri", "9900", 2026,
                          "https://www.vergiport.com/yeni", "2026 siniri 9900")
    result3 = decide([old, new_a, new_b, third])  # 4 sources total
    assert result3.status == "verified"
    assert result3.effective_year == 2026

    conflict = FactCandidate("fatura siniri", "10000", 2026,
                             "https://www.vergiport.com/yeni", "2026 siniri 10000")
    # 2 sources same value + 1 conflicting -> conflict (eski: verified)
    assert decide([new_a, new_b, conflict]).status == "conflict"

    second_conflict = FactCandidate("fatura siniri", "10000", 2026,
                                     "https://www.pkf.com.tr/yeni", "2026 siniri 10000")
    # 2 values with 2 sources each -> conflict
    assert decide([new_a, new_b, conflict, second_conflict]).status == "conflict"

    # aynı değerin farklı yazımı (nokta/virgül, ondalık var/yok) yanlışlıkla "çelişkili"
    # sayılmamalı -- gerçek vakada "12.000 TL" ile "12.000,00 TL" iki bağımsız kaynaktan
    # geldiği halde farklı biçim yüzünden yanlış "conflict" veriyordu (bkz. accounting_knowledge
    # canlı taramasında vuk_313_amortisman_siniri 2026)
    plain = FactCandidate("demirbas siniri", "12.000 TL", 2026,
                          "https://www.muhasebetr.com/demirbas", "2026 siniri 12.000 TL")
    with_decimals = FactCandidate("demirbas siniri", "12.000,00 TL", 2026,
                                  "https://pkf.com.tr/demirbas", "2026 siniri 12.000,00 TL")
    same_format_result = decide([plain, with_decimals])
    # 2 sources same normalized value -> partially_verified (eski: verified)
    assert same_format_result.status == "partially_verified"
    assert len(same_format_result.sources) == 2

    print("KAIZEN MUHASEBE UZLASI TESTI: BASARILI")


def test_accounting_consensus_percent_decimal_point_not_confused_with_thousands():
    """DÜZELTME (2026-09-23): sayı ayrıştırma hatası -- "%4.5" (dört virgül beş) ile "%45"
    (kırk beş) eskiden AYNI değer sayılıyordu, çünkü tek "." her zaman binlik ayıracı kabul
    edilip siliniyordu ("4.5" -> "45"). Bu iki gerçekten FARKLI orandır; aynı (konu, yıl) için
    ikisi de görülürse "conflict"/"pending_confirmation" olmalı, sessizce birleşmemeli."""
    decide = AccountingConsensus().decide

    dotted = FactCandidate("gecikme faizi", "%4.5", 2026,
                           "https://www.muhasebetr.com/oran", "Gecikme faizi aylık %4.5")
    forty_five = FactCandidate("gecikme faizi", "%45", 2026,
                               "https://www.alomaliye.com/oran", "Gecikme faizi aylık %45")
    result = decide([dotted, forty_five])
    assert result.status in ("conflict", "single_source")
    assert result.value is None  # tek bir "doğrulanmış" değer üretilmemeli

    # ama nokta ve virgülle yazılmış AYNI oran (%4.5 / %4,5) hâlâ tek bir değer olarak birleşmeli
    comma_form = FactCandidate("gecikme faizi", "%4,5", 2026,
                               "https://www.pkf.com.tr/oran", "Gecikme faizi aylık %4,5")
    merged = decide([dotted, comma_form])
    assert merged.status == "partially_verified"
    assert len(merged.sources) == 2

    # oran ile parasal tutar birbirine karışmamalı ("%20" ile "20 TL" aynı grup sayılmamalı)
    percent_20 = FactCandidate("karma test", "%20", 2026, "https://www.muhasebetr.com/x", "%20")
    tl_20 = FactCandidate("karma test", "20 TL", 2026, "https://www.alomaliye.com/x", "20 TL")
    mixed = decide([percent_20, tl_20])
    assert mixed.status in ("conflict", "single_source")

    print("KAIZEN UZLASI YUZDE NOKTA/VIRGUL TESTI: BASARILI")


if __name__ == "__main__":
    test_accounting_consensus()
    test_accounting_consensus_percent_decimal_point_not_confused_with_thousands()