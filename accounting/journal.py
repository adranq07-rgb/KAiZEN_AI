"""Yevmiye kaydı motoru: çift taraflı kayıt, doğrulama ve sık kullanılan şablonlar.

Her kayıt Tek Düzen Hesap Planı'na karşı doğrulanır ve borç = alacak şartı
kuruşu kuruşuna denetlenir. Oranlar hiçbir zaman sabit değildir; çağıran verir.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from accounting.calculators import CalculationError, D, _extract, kdv, money
from accounting.chart_of_accounts import ChartOfAccounts
from core.text_tr import fold_tr, format_number_tr, format_tl

ZERO = Decimal("0.00")


class JournalError(ValueError):
    pass


@dataclass
class JournalLine:
    account: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    memo: str = ""


@dataclass
class JournalEntry:
    description: str
    lines: list = field(default_factory=list)
    entry_date: date | None = None
    notes: list = field(default_factory=list)

    def debit(self, account, amount, memo=""):
        amount = money(amount)
        if amount:
            self.lines.append(JournalLine(account, debit=amount, memo=memo))
        return self

    def credit(self, account, amount, memo=""):
        amount = money(amount)
        if amount:
            self.lines.append(JournalLine(account, credit=amount, memo=memo))
        return self

    @property
    def total_debit(self):
        return sum((l.debit for l in self.lines), ZERO)

    @property
    def total_credit(self):
        return sum((l.credit for l in self.lines), ZERO)

    def validate(self, chart=None):
        chart = chart or ChartOfAccounts()
        if len(self.lines) < 2:
            raise JournalError("Yevmiye kaydı en az iki satır içermeli")
        for line in self.lines:
            if line.account not in chart:
                raise JournalError(f"Hesap planında {line.account} kodlu hesap yok")
            if (line.debit > 0) == (line.credit > 0):
                raise JournalError(f"{line.account}: satır ya borç ya alacak olmalı")
            if line.debit < 0 or line.credit < 0:
                raise JournalError(f"{line.account}: tutar negatif olamaz")
        if self.total_debit != self.total_credit:
            raise JournalError(
                f"Borç ({format_tl(self.total_debit)}) alacağa ({format_tl(self.total_credit)}) eşit değil"
            )
        return True

    def render(self, chart=None, width=44):
        chart = chart or ChartOfAccounts()
        header = f"{'HESAP':<{width}}{'BORÇ':>16}{'ALACAK':>16}"
        rows = [header]
        for line in sorted(self.lines, key=lambda l: (l.credit > 0)):
            account = chart.get(line.account)
            label = f"{line.account} {account.clean_name() if account else '?'}"
            if line.credit > 0:
                label = "    " + label
            debit = format_number_tr(line.debit) if line.debit else ""
            credit = format_number_tr(line.credit) if line.credit else ""
            rows.append(f"{label:<{width}}{debit:>16}{credit:>16}")
        rows.append(f"{'TOPLAM':<{width}}{format_number_tr(self.total_debit):>16}{format_number_tr(self.total_credit):>16}")
        text = f"YEVMİYE KAYDI — {self.description}\n" + "\n".join(rows)
        if self.notes:
            text += "\nNOT: " + " ".join(self.notes)
        return text


# --- Şablonlar --------------------------------------------------------------------

_SETTLEMENT = {"vadeli": None, "nakit": "100", "banka": "102"}


def _settle_credit(entry, mode, amount, payable_account):
    if mode not in _SETTLEMENT:
        raise JournalError("Ödeme şekli 'vadeli', 'nakit' veya 'banka' olmalı")
    entry.credit(_SETTLEMENT[mode] or payable_account, amount)


def purchase_goods(net, kdv_rate, mode="vadeli", stock_account="153", description=None):
    """Ticari mal alışı: mal (net) + indirilecek KDV borç, satıcı/kasa/banka alacak."""
    tax = kdv(net, kdv_rate)
    entry = JournalEntry(description or "Ticari mal alışı")
    entry.debit(stock_account, tax["matrah"]).debit("191", tax["kdv"])
    _settle_credit(entry, mode, tax["toplam"], "320")
    return entry


def expense_invoice(net, kdv_rate, mode="vadeli", expense_account="770", description=None):
    """Gider faturası (kira, elektrik vb.). 7/A seçeneğinde 770; dönem sonunda 632'ye yansıtılır."""
    tax = kdv(net, kdv_rate)
    entry = JournalEntry(description or "Gider faturası")
    entry.debit(expense_account, tax["matrah"]).debit("191", tax["kdv"])
    _settle_credit(entry, mode, tax["toplam"], "320")
    if expense_account.startswith("77"):
        entry.notes.append("7/A seçeneğinde dönem sonunda 632 B / 771 A ve 771 B / 770 A ile gelir tablosuna yansıtılır.")
    return entry


def sale_goods(net, kdv_rate, mode="vadeli", cost=None, description=None):
    """Mal satışı: alıcı/kasa/banka borç, satışlar + hesaplanan KDV alacak (+ istenirse maliyet kaydı)."""
    tax = kdv(net, kdv_rate)
    entry = JournalEntry(description or "Ticari mal satışı")
    receivable = _SETTLEMENT.get(mode, "x")
    if receivable == "x":
        raise JournalError("Tahsilat şekli 'vadeli', 'nakit' veya 'banka' olmalı")
    entry.debit(receivable or "120", tax["toplam"])
    entry.credit("600", tax["matrah"]).credit("391", tax["kdv"])
    if cost is not None:
        entry.debit("621", cost).credit("153", cost)
        entry.notes.append("Satılan malın maliyeti sürekli envanter yöntemiyle 621 B / 153 A kaydedildi.")
    return entry


def sales_return(net, kdv_rate, mode="vadeli", description=None):
    tax = kdv(net, kdv_rate)
    entry = JournalEntry(description or "Satıştan iade")
    entry.debit("610", tax["matrah"]).debit("391", tax["kdv"])
    entry.credit(_SETTLEMENT.get(mode) or "120", tax["toplam"])
    return entry


def collection(amount, via="banka", description=None):
    entry = JournalEntry(description or "Alıcıdan tahsilat")
    entry.debit("100" if via == "nakit" else "102", amount).credit("120", amount)
    return entry


def payment(amount, via="banka", description=None):
    entry = JournalEntry(description or "Satıcıya ödeme")
    entry.debit("320", amount).credit("100" if via == "nakit" else "102", amount)
    return entry


def depreciation(amount, expense_account="770", accumulated_account="257", description=None):
    entry = JournalEntry(description or "Amortisman gideri")
    entry.debit(expense_account, amount).credit(accumulated_account, amount)
    return entry


def kdv_settlement(hesaplanan, indirilecek, description=None):
    """Dönem sonu KDV mahsubu: 391 ile 191 karşılaştırılır; fark 360'a ya da 190'a gider."""
    hesaplanan, indirilecek = money(hesaplanan), money(indirilecek)
    entry = JournalEntry(description or "KDV mahsubu")
    entry.debit("391", hesaplanan).credit("191", indirilecek)
    if hesaplanan > indirilecek:
        entry.credit("360", hesaplanan - indirilecek)
        entry.notes.append("Fark ödenecek KDV olarak 360 Ödenecek Vergi ve Fonlar'a alındı.")
    elif indirilecek > hesaplanan:
        entry.debit("190", indirilecek - hesaplanan)
        entry.notes.append("Fark bir sonraki döneme 190 Devreden KDV olarak taşındı.")
    return entry


def salary_accrual(gross, sgk_worker, income_tax, stamp_tax, description=None):
    """Ücret tahakkuku: brüt ücret gider; kesintiler ve net ücret borç hesaplarına alacak."""
    gross, sgk_worker = money(gross), money(sgk_worker)
    income_tax, stamp_tax = money(income_tax), money(stamp_tax)
    net = gross - sgk_worker - income_tax - stamp_tax
    if net < 0:
        raise JournalError("Kesintiler brüt ücreti aşıyor")
    entry = JournalEntry(description or "Ücret tahakkuku")
    entry.debit("770", gross)
    entry.credit("361", sgk_worker).credit("360", income_tax + stamp_tax).credit("335", net)
    return entry


def employer_sgk(amount, description=None):
    entry = JournalEntry(description or "İşveren SGK payı tahakkuku")
    entry.debit("770", amount).credit("361", amount)
    return entry


def capital_contribution(amount, via="banka", description=None):
    entry = JournalEntry(description or "Sermaye ödemesi")
    entry.debit("100" if via == "nakit" else "102", amount).credit("500", amount)
    return entry


def bank_loan(amount, long_term=False, description=None):
    entry = JournalEntry(description or "Banka kredisi kullanımı")
    entry.debit("102", amount).credit("400" if long_term else "300", amount)
    return entry


def purchase_return(net, kdv_rate, mode="vadeli", description=None):
    """Alıştan iade: satıcı/kasa/banka borç; mal (net) ve indirilecek KDV alacak (KDV indirimi geri alınır)."""
    tax = kdv(net, kdv_rate)
    entry = JournalEntry(description or "Alıştan iade")
    entry.debit(_SETTLEMENT.get(mode) or "320", tax["toplam"])
    entry.credit("153", tax["matrah"]).credit("191", tax["kdv"])
    return entry


_ASSET_ACCOUNTS = (
    (("bilgisayar", "demirbas", "mobilya", "yazici", "telefon", "masa", "koltuk", "klima", "laptop"), "255"),
    (("arac", "otomobil", "kamyon", "kamyonet", "tasit", "minibus", "traktor"), "254"),
    (("makine", "tezgah", "cnc", "pres"), "253"),
    (("bina",), "252"),
    (("arsa", "arazi"), "250"),
)


def asset_account_for(folded):
    for words, account in _ASSET_ACCOUNTS:
        if any(re.search(rf"\b{w}\w*", folded) for w in words):
            return account
    return None


def fixed_asset_purchase(net, kdv_rate, mode="vadeli", account="255", description=None):
    """Sabit kıymet alımı: 25x hesabı (net) ve 191 borç; satıcı (veya kasa/banka) alacak."""
    tax = kdv(net, kdv_rate)
    entry = JournalEntry(description or "Sabit kıymet alımı")
    entry.debit(account, tax["matrah"]).debit("191", tax["kdv"])
    _settle_credit(entry, mode, tax["toplam"], "320")
    if account == "254":
        entry.notes.append("Binek otomobillerde KDV indirimi ve gider/amortisman kısıtları mevzuata bağlıdır; "
                           "güncel sınırlar için 'binek araç gider kısıtlaması' diye sorun. Burada KDV 191'e alındı.")
    if account == "250":
        entry.notes.append("Arsa amortismana tabi değildir.")
    return entry


def partner_loan_in(amount, via="banka", description=None):
    entry = JournalEntry(description or "Ortaklardan borç alındı")
    entry.debit("100" if via == "nakit" else "102", amount).credit("331", amount)
    return entry


def partner_loan_repay(amount, via="banka", description=None):
    entry = JournalEntry(description or "Ortaklara borç ödemesi")
    entry.debit("331", amount).credit("100" if via == "nakit" else "102", amount)
    return entry


def cash_shortage(amount, description=None):
    entry = JournalEntry(description or "Kasa noksanı")
    entry.debit("197", amount).credit("100", amount)
    entry.notes.append("Noksanın nedeni bulunursa ilgili hesaba aktarılır; bulunamazsa dönem sonunda 689 Diğer Olağan Gider ve Zararlar'a alınır.")
    return entry


def cash_excess(amount, description=None):
    entry = JournalEntry(description or "Kasa fazlası")
    entry.debit("100", amount).credit("397", amount)
    entry.notes.append("Fazlanın nedeni bulunursa ilgili hesaba aktarılır; bulunamazsa dönem sonunda 679 Diğer Olağan Gelir ve Karlar'a alınır.")
    return entry


def cash_deposit(amount, description=None):
    entry = JournalEntry(description or "Kasadan bankaya para yatırma")
    entry.debit("102", amount).credit("100", amount)
    return entry


# --- Doğal dil yönlendirici --------------------------------------------------------

def _mode(folded, default="vadeli"):
    if any(w in folded for w in ("nakit", "kasadan", "kasaya", "pesin")):
        return "nakit"
    if any(w in folded for w in ("banka", "havale", "eft", "kredi karti")):
        return "banka"
    return default


class JournalRouter:
    """'10.000 TL + %20 KDV ile mal alındı, yevmiye kaydı nedir?' türü soruları cevaplar."""

    def __init__(self, chart=None):
        self.chart = chart or ChartOfAccounts()

    def answer(self, question):
        info = _extract(question)
        folded = info["folded"]
        if not any(k in folded for k in ("yevmiye", "muhasebe kayd", "kaydi", "kayit", "hangi hesap", "borc", "alacak")):
            return None
        amounts, rates = info["amounts"], info["rates"]
        try:
            entry = self._build(folded, amounts, rates, info)
        except (JournalError, CalculationError) as exc:
            return f"Kaizen: Kayıt oluşturulamadı: {exc}"
        if entry is None:
            return None
        if isinstance(entry, str):
            return entry
        entry.validate(self.chart)
        uses_kdv = any(line.account in ("191", "391") for line in entry.lines)
        basis = ("Tek Düzen Hesap Planı ve KDV Kanunu uygulaması (oran soruda verildiği gibi kullanıldı)."
                 if uses_kdv else "Tek Düzen Hesap Planı.")
        return f"SONUÇ:\n{entry.render(self.chart)}\nDAYANAK: {basis}"

    def _net_amount(self, folded, amounts, rates):
        """Soruda KDV dahil tutar verildiyse matrahı bulur."""
        amount = amounts[0]
        if "kdv dahil" in folded and "haric" not in folded and rates:
            return kdv(amount, rates[0], included=True)["matrah"]
        return amount

    def _build(self, folded, amounts, rates, info):
        need_amount = "Kaizen: Tutarı belirtmediniz; kaydı tutar uydurmadan oluşturamam."
        need_rate = "Kaizen: KDV oranını belirtmediniz (ör. %20); oranı uydurmadan kayıt oluşturamam."
        if "iade" in folded and any(k in folded for k in ("alis", "alim", "alinan")) and "satis" not in folded:
            if not amounts:
                return need_amount
            if not rates:
                return need_rate
            return purchase_return(self._net_amount(folded, amounts, rates), rates[0], _mode(folded))
        asset = asset_account_for(folded)
        if asset and any(k in folded for k in ("aldim", "aldik", "alindi", "satin", "alis", "alim")):
            if not amounts:
                return need_amount
            if not rates:
                return need_rate
            return fixed_asset_purchase(self._net_amount(folded, amounts, rates), rates[0], _mode(folded), asset)
        if re.search(r"\borta[gk]\w*", folded) and "borc" in folded and any(
            k in folded for k in ("alindi", "aldik", "aldim", "alinan", "verildi", "verdik", "odendi", "odedik", "odeme", "geri")
        ):
            if not amounts:
                return need_amount
            if any(k in folded for k in ("odendi", "odeme", "geri", "iade")):
                return partner_loan_repay(amounts[0], _mode(folded, "banka"))
            return partner_loan_in(amounts[0], _mode(folded, "banka"))
        if "kasa" in folded and any(k in folded for k in ("noksan", "eksik", "acik")):
            return cash_shortage(amounts[0]) if amounts else need_amount
        if "kasa" in folded and any(k in folded for k in ("fazla", "fazlasi", "fazlalik")):
            return cash_excess(amounts[0]) if amounts else need_amount
        if "yatir" in folded and "banka" in folded and "kasa" in folded:
            return cash_deposit(amounts[0]) if amounts else need_amount
        if any(k in folded for k in ("mal alindi", "mal aldik", "mal alis", "mal alimi", "emtia alis", "alis faturasi", "ticari mal alis")):
            if not amounts:
                return need_amount
            if not rates:
                return need_rate
            return purchase_goods(self._net_amount(folded, amounts, rates), rates[0], _mode(folded))
        if any(k in folded for k in ("mal satildi", "mal sattik", "satis faturasi", "satis yapildi", "mal satis", "satis kayd")):
            if not amounts:
                return need_amount
            if not rates:
                return need_rate
            cost = None
            match = re.search(r"maliyet\w*\s*(\d[\d.,]*)", folded)
            if match:
                cost = D(match.group(1).replace(".", "").replace(",", "."))
            net = self._net_amount(folded, [a for a in amounts if a != cost] or amounts, rates)
            return sale_goods(net, rates[0], _mode(folded), cost=cost)
        if "iade" in folded and "satis" in folded:
            if not amounts:
                return need_amount
            if not rates:
                return need_rate
            return sales_return(self._net_amount(folded, amounts, rates), rates[0], _mode(folded))
        if any(k in folded for k in ("gider fatura", "kira gider", "elektrik", "su fatura", "telefon fatura", "kira bedel")):
            if not amounts:
                return need_amount
            if not rates:
                return need_rate
            return expense_invoice(self._net_amount(folded, amounts, rates), rates[0], _mode(folded))
        if "tahsilat" in folded:
            return collection(amounts[0], _mode(folded, "banka")) if amounts else need_amount
        if "odeme" in folded and any(w in folded for w in ("satici", "tedarikci", "borc")):
            return payment(amounts[0], _mode(folded, "banka")) if amounts else need_amount
        if "amortisman" in folded and any(w in folded for w in ("ayrildi", "kayit", "gider", "yevmiye")):
            return depreciation(amounts[0]) if amounts else need_amount
        if "mahsup" in folded and "kdv" in folded:
            h = re.search(r"hesaplanan\D*(\d[\d.,]*)", folded)
            i = re.search(r"indirilecek\D*(\d[\d.,]*)", folded)
            if not (h and i):
                return "Kaizen: KDV mahsubu için hesaplanan ve indirilecek KDV tutarlarını yazın."
            return kdv_settlement(D(h.group(1).replace(".", "").replace(",", ".")),
                                  D(i.group(1).replace(".", "").replace(",", ".")))
        if "sermaye" in folded and any(w in folded for w in ("odendi", "yatirildi", "konuldu", "tahsil")):
            return capital_contribution(amounts[0], _mode(folded, "banka")) if amounts else need_amount
        if "kredi" in folded and any(w in folded for w in ("kullan", "cekil", "alindi")):
            return bank_loan(amounts[0], long_term="uzun vadeli" in folded) if amounts else need_amount
        return None
