from decimal import Decimal

from accounting import calculators as calc
from core.text_tr import parse_tr_number, format_tl


def test_calculators():
    # KDV
    r = calc.kdv("1000", 20)
    assert (r["kdv"], r["toplam"]) == (Decimal("200.00"), Decimal("1200.00"))
    r = calc.kdv("1200", 20, included=True)
    assert (r["matrah"], r["kdv"]) == (Decimal("1000.00"), Decimal("200.00"))
    r = calc.kdv("100", 10, included=True)   # 100/1,10 = 90,909... -> 90,91
    assert (r["matrah"], r["kdv"]) == (Decimal("90.91"), Decimal("9.09"))
    # tevkifat 5/10 : 1000 matrah, %20 KDV -> 200 KDV, 100 tevkifat
    t = calc.kdv_tevkifat(1000, 20, 5, 10)
    assert (t["hesaplanan_kdv"], t["tevkifat_kdv"], t["satici_kdv"]) == (
        Decimal("200.00"), Decimal("100.00"), Decimal("100.00"))
    # stopaj / SMM
    assert calc.stopaj(1000, 20)["net"] == Decimal("800.00")
    assert calc.stopaj(800, 20, amount_is_net=True)["brut"] == Decimal("1000.00")
    s = calc.serbest_meslek_makbuzu(1000, 20, 20)
    assert s["net_tahsilat"] == Decimal("1000.00")
    assert calc.serbest_meslek_makbuzu_netten(1000, 20, 20)["brut"] == Decimal("1000.00")
    assert calc.damga_vergisi(100000, "9.48") == Decimal("948.00")
    # Faiz / iskonto
    assert calc.basit_faiz(10000, 36.5, 100)["faiz"] == Decimal("1000.00")
    assert calc.gecikme_zammi(1000, 4, 3)["gecikme_zammi"] == Decimal("120.00")
    assert calc.iskonto(36500, 10, 100, kind="dis")["iskonto"] == Decimal("1000.00")
    assert calc.iskonto(36500, 10, 100, kind="ic")["iskonto"] == Decimal("973.33")
    # Amortisman: normal 5 yıl, azalan 5 yıl
    rows = calc.depreciation_schedule(100000, 5)
    assert [r["amortisman"] for r in rows] == [Decimal("20000.00")] * 5
    assert rows[-1]["net_deger"] == Decimal("0.00")
    rows = calc.depreciation_schedule(100000, 5, "azalan")   # oran %40
    assert [r["amortisman"] for r in rows] == [
        Decimal("40000.00"), Decimal("24000.00"), Decimal("14400.00"),
        Decimal("8640.00"), Decimal("12960.00")]
    assert sum(r["amortisman"] for r in rows) == Decimal("100000.00")
    rows = calc.depreciation_schedule(120000, 4, "normal", first_year_months=6)  # kıst
    assert rows[0]["amortisman"] == Decimal("15000.00") and len(rows) == 5
    assert sum(r["amortisman"] for r in rows) == Decimal("120000.00")
    # Kredi
    loan = calc.loan_schedule(12000, 0, 12)
    assert all(r["taksit"] == Decimal("1000.00") for r in loan) and loan[-1]["kalan"] == 0
    loan = calc.loan_schedule(10000, 2, 6)
    assert sum(r["anapara"] for r in loan) == Decimal("10000.00") and loan[-1]["kalan"] == 0
    # Yatırım
    assert calc.npv(10, [-1000, 1100]).quantize(Decimal("0.01")) == Decimal("0.00")
    assert calc.irr([-1000, 1100]) == Decimal("10.0000")
    assert calc.break_even(10000, 50, 30)["adet"] == Decimal("500")
    assert calc.percent_change(200, 250) == Decimal("25.00")
    # Sayı ayrıştırma ve biçim
    assert parse_tr_number("10.000,50") == Decimal("10000.50")
    assert parse_tr_number("1.500") == Decimal("1500")
    assert parse_tr_number("2,5") == Decimal("2.5")
    assert format_tl(Decimal("1234567.5")) == "1.234.567,50 TL"

    # Doğal dil yönlendirici
    router = calc.CalculatorRouter()
    out = router.answer("1.200 TL KDV dahil tutarın KDV'sini hesapla %20")
    assert "Matrah 1.000,00 TL" in out and "200,00 TL" in out
    out = router.answer("1000 TL kdv hesapla")
    assert "oranını belirtmediniz" in out           # oran uydurulmaz
    out = router.answer("100.000 TL maliyetli demirbaş 5 yıl azalan bakiyeler amortisman planı")
    assert "40.000,00" in out and "12.960,00" in out
    assert router.answer("Kasa hesabı nedir?") is None
    assert "800,00 TL" in router.answer("1000 TL brüt üzerinden %20 stopaj hesapla")
    assert "100,00 TL" in router.answer("1000 TL matrah 5/10 tevkifat %20 kdv hesapla")
    try:
        calc.kdv(-1, 20)
        assert False
    except calc.CalculationError:
        pass

    print("KAIZEN HESAPLAYICI TESTI: BASARILI")


if __name__ == "__main__":
    test_calculators()
