from decimal import Decimal

from accounting.chart_of_accounts import ChartOfAccounts
from accounting import journal as j


def _sums(entry):
    per = {}
    for line in entry.lines:
        per[line.account] = per.get(line.account, Decimal("0")) + (line.debit - line.credit)
    return per


def test_journal():
    chart = ChartOfAccounts()
    assert len(chart) > 250 and chart.get("153").clean_name() == "Ticari Mallar"
    assert chart.get("257").contra and chart.get("257").normal_balance == "alacak"
    assert chart.get("153.01").code == "153"           # alt hesap ana hesaba iner

    entry = j.purchase_goods("10000", 20)
    entry.validate(chart)
    assert _sums(entry) == {"153": Decimal("10000.00"), "191": Decimal("2000.00"), "320": Decimal("-12000.00")}
    entry = j.purchase_goods("10000", 20, mode="nakit")
    assert _sums(entry)["100"] == Decimal("-12000.00")

    sale = j.sale_goods("5000", 20, cost="3000")
    sale.validate(chart)
    assert _sums(sale) == {
        "120": Decimal("6000.00"), "600": Decimal("-5000.00"), "391": Decimal("-1000.00"),
        "621": Decimal("3000.00"), "153": Decimal("-3000.00"),
    }
    assert j.sales_return("1500", 18).total_debit == Decimal("1770.00")   # notlardaki 610/191... örneği

    a = j.kdv_settlement("5000", "3000")
    a.validate(chart)
    assert _sums(a)["360"] == Decimal("-2000.00")
    b = j.kdv_settlement("3000", "5000")
    b.validate(chart)
    assert _sums(b)["190"] == Decimal("2000.00")

    pay = j.salary_accrual("30000", "4200", "3500", "227.70")
    pay.validate(chart)
    assert _sums(pay)["335"] == Decimal("-22072.30")
    j.depreciation("1666.67").validate(chart)

    # Dengesiz veya geçersiz kayıtlar reddedilir
    bad = j.JournalEntry("Bozuk").debit("100", "100").credit("102", "99.99")
    try:
        bad.validate(chart)
        assert False
    except j.JournalError as exc:
        assert "eşit değil" in str(exc)
    try:
        j.JournalEntry("Yanlış hesap").debit("999", "1").credit("100", "1").validate(chart)
        assert False
    except j.JournalError as exc:
        assert "999" in str(exc)

    router = j.JournalRouter(chart)
    out = router.answer("10.000 TL + %20 KDV ile vadeli mal alındı, yevmiye kaydı nedir?")
    assert "153 Ticari Mallar" in out and "12.000,00" in out and "320 Satıcılar" in out
    out = router.answer("12.000 TL KDV dahil %20 nakit mal satıldı maliyeti 6.000 TL kaydı")
    assert "100 Kasa" in out and "10.000,00" in out and "621" in out
    assert "KDV oranını belirtmediniz" in router.answer("10.000 TL mal alındı yevmiye kaydı")
    assert router.answer("Enflasyon nedir?") is None
    print("KAIZEN YEVMIYE TESTI: BASARILI")


if __name__ == "__main__":
    test_journal()
