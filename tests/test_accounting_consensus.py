from accounting.consensus import AccountingConsensus, FactCandidate


def test_accounting_consensus():
    decide = AccountingConsensus().decide
    old = FactCandidate("fatura siniri", "6900", 2025,
                        "https://www.muhasebetr.com/eski", "2025 siniri 6900")
    new_a = FactCandidate("fatura siniri", "9900", 2026,
                          "https://www.muhasebetr.com/yeni", "2026 siniri 9900")
    assert decide([old, new_a]).status == "pending_confirmation"

    new_b = FactCandidate("fatura siniri", "9.900", 2026,
                          "https://www.alomaliye.com/makaleler/yeni", "2026 siniri 9.900")
    result = decide([old, new_a, new_b])
    assert result.status == "verified"
    assert result.effective_year == 2026

    official = FactCandidate("kurumlar vergisi", "%25", 2026,
                             "https://www.gib.gov.tr/oran", "Genel oran %25")
    assert decide([official]).status == "verified"

    conflict = FactCandidate("fatura siniri", "10000", 2026,
                             "https://www.vergiport.com/yeni", "2026 siniri 10000")
    assert decide([new_a, new_b, conflict]).status == "verified"

    second_conflict = FactCandidate("fatura siniri", "10000", 2026,
                                    "https://www.pkf.com.tr/yeni", "2026 siniri 10000")
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
    assert same_format_result.status == "verified"
    assert len(same_format_result.sources) == 2

    print("KAIZEN MUHASEBE UZLASI TESTI: BASARILI")


if __name__ == "__main__":
    test_accounting_consensus()
