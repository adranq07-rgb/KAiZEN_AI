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
    source_reference: str = ""

    def __post_init__(self):
        for name in ("debit", "credit"):
            value = getattr(self, name)
            if isinstance(value, (float, bool)):
                raise JournalError("Para tutarı float olamaz; Decimal kullanın")
            value = money(value)
            if not value.is_finite():
                raise JournalError("Para tutarı sonlu olmalı")
            setattr(self, name, value)


@dataclass
class JournalEntry:
    description: str
    lines: list = field(default_factory=list)
    entry_date: date | None = None
    notes: list = field(default_factory=list)

    def debit(self, account, amount, memo=""):
        if isinstance(amount, (float, bool)):
            raise JournalError("Para tutarı float olamaz; Decimal kullanın")
        amount = money(amount)
        if amount:
            self.lines.append(JournalLine(account, debit=amount, memo=memo))
        return self

    def credit(self, account, amount, memo=""):
        if isinstance(amount, (float, bool)):
            raise JournalError("Para tutarı float olamaz; Decimal kullanın")
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
            if any(not isinstance(v, Decimal) or not v.is_finite() or v != money(v)
                   for v in (line.debit, line.credit)):
                raise JournalError("Tutarlar sonlu, kuruş hassasiyetinde Decimal olmalı")
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
        self.validate(chart)
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

    def to_dict(self, chart=None):
        chart = chart or ChartOfAccounts()
        self.validate(chart)
        return {"description": self.description, "status": "PROPOSED",
                "entry_date": self.entry_date.isoformat() if self.entry_date else None,
                "lines": [{"account_code": l.account, "account_name": chart.get(l.account).clean_name(),
                           "debit": str(l.debit), "credit": str(l.credit),
                           "rationale": l.memo, "source_reference": l.source_reference} for l in self.lines],
                "debit_total": str(self.total_debit), "credit_total": str(self.total_credit),
                "notes": self.notes}


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

    def __init__(self, chart=None, principle_registry=None):
        self.chart = chart or ChartOfAccounts()
        self.principle_registry = principle_registry
        self.last_result = None

    def answer(self, question):
        self.last_result = None
        info = _extract(question)
        folded = info["folded"]
        event_answer = self._event_answer(question, info)
        if event_answer is not None:
            return event_answer
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
        try:
            entry.validate(self.chart)
        except JournalError as exc:
            self.last_result = {"status": "INVALID", "invariant_failures": [str(exc)]}
            return f"Kaizen: Kayıt oluşturulamadı: {exc}"
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
        need_rate = "Kaizen: KDV oranını belirtmediniz; oranı uydurmadan kayıt oluşturamam."
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


    def _event_answer(self, question, info):
        """Resolve a single stated economic event before the legacy keyword router."""
        text = info['folded']
        event = None
        acquire = bool(re.search(r"\b(?:aldim|aldik|aldi|alindi|alinmis|alim[ia]?|alis|aldigim|satin al\w*)\b", text))
        negative = bool(re.search(r"\b(?:almad\w*|alinmad\w*|almay\w*)\b", text))
        deposit = bool(re.search(r"\byatir\w*", text)) and 'banka' in text and 'kasa' in text
        collection_event = bool(re.search(r"\b(?:tahsil\w*|tahsilat)\b", text))
        payment_event = bool(re.search(r"\b(?:odedim|odedik|odendi|odeme|oduyorum)\b", text))
        goods = bool(re.search(r"\b(?:mal[ıi]?|mallar\w*|emtia|stok\w*)\b", text))
        asset = asset_account_for(text)
        expense = bool(re.search(r"\b(?:gider\w*|elektrik|kira|hizmet|su faturasi)\b", text))
        amounts = _extract(re.sub(r"\b7/[ab]\b", " ", question, flags=re.I))['amounts']
        # Keep unquantified conceptual explanations in the existing source-backed solver.
        if not amounts:
            return None
        if re.search(r"\b(?:ortak\w*|kredi)\b", text) and acquire and not goods and not asset:
            return None  # Existing financing templates, not an acquisition of goods/services.
        if deposit:
            event = 'cash_deposit'
        elif collection_event:
            event = 'customer_collection' if re.search(r"\b(?:musteri\w*|alici\w*)\b", text) else 'unknown_collection'
        elif payment_event and re.search(r"\b(?:satici\w*|tedarikci\w*)\b", text) and not acquire and not expense:
            event = 'vendor_payment'
        elif acquire and not negative and 'iade' not in text:
            if re.search(r"\b(?:satmak|yeniden satis|satis amaciyla)\b", text):
                event = 'purchase'
            elif goods and asset:
                event = 'ambiguous_acquisition'
            elif goods:
                event = 'purchase'
            elif asset:
                event = 'asset_purchase'
            elif expense:
                event = 'expense'
            else:
                event = 'ambiguous_acquisition'
        elif expense and any(w in text for w in ('fatura', 'odedim', 'odendi')) and not any(w in text for w in ('amortisman', 'kisit', 'indir', 'stopaj', 'ne kadar', 'nedir')):
            event = 'expense'
        elif payment_event and 'borc' in text and not any(w in text for w in ('ortak', 'kredi', 'vergi', 'sgk')):
            event = 'unknown_payment'
        if event is None:
            return None
        state = {'event':event,'status':'CLARIFICATION','known_facts':{},'missing_information':[],
                 'assumptions':[], 'principles':[], 'invariant_failures':[], 'journal':None,
                 'knowledge_types':{'stable':['double_entry','TDHP'], 'context':['event','payment','amount_basis'],
                                    'current':[]}}
        self.last_result = state
        def ask(fact, message):
            state['missing_information'] = [fact]
            return 'Kaizen: '+message
        negated_event = (event == 'cash_deposit' and re.search(r"\byatir(?:ma|ilma|may)\w*", text)
                         or event in ('customer_collection', 'unknown_collection') and re.search(r"\btahsil\s+(?:etme|edilme|edeme)\w*", text)
                         or event in ('vendor_payment', 'unknown_payment') and re.search(r"\b(?:odemedi|odenmedi|odemeye)\w*", text))
        if negated_event:
            return ask('event_occurred', 'İşlemin gerçekleşmediğini belirtiyorsunuz. Gerçekleşen işlem nedir? Gerçekleşmemiş ödeme/tahsilat için kayıt oluşturmuyorum.')
        if event == 'cash_deposit' and not ('kasadan' in text and 'bankaya' in text):
            return ask('transfer_direction', 'Bu şablon kasadan bankaya yatırmayı destekliyor. Paranın hangi hesaptan hangi hesaba geçtiğini netleştirin; ters yönde kayıt oluşturamam.')
        if event == 'ambiguous_acquisition':
            return ask('transaction_nature','Alınan şey satılacak ticari mal mı, işletmede kullanılacak demirbaş mı, yoksa hizmet/gider mi?')
        if event in ('unknown_payment','unknown_collection'):
            return ask('counterparty_role','İşlem müşteriden alacak tahsilatı mı, satıcıya borç ödemesi mi? Karşı tarafı belirtin.')
        if len(amounts) != 1:
            return ask('single_amount','Bu tek işlem için esas alınacak tutar hangisi? Birden fazla tutar veya sayı var.')
        amount=amounts[0]
        if re.search(r"-\s*\d", text) or amount<=0:
            state.update(status='INVALID',invariant_failures=['non_positive_amount'])
            return 'Kaizen: Kayıt oluşturulamadı: işlem tutarı pozitif olmalı.'
        state['known_facts']['amount']=str(amount)
        if any(w in text for w in ('kismen', 'bir kismini', 'taksit', 'cek ile', 'senet', 'kredi kart')):
            return ask('settlement_details','Kısmi ödeme, taksit, çek/senet veya kart için ödeme dağılımı ve ilgili hesap bilgilerini belirtin; tek ödeme hesabı varsayamam.')
        if any(w in text for w in ('gecen ay', 'gelecek ay', 'gecen yil', 'gelecek yil')):
            return ask('document_period','Belge tarihi ve malın teslim/hizmetin ait olduğu dönem nedir? Ödeme tarihi tek başına kayıt dönemini belirlemez.')
        taxable = event in ('purchase','asset_purchase','expense')
        rates=info['rates']
        if taxable and not rates:
            state['knowledge_types']['current']=['applicable_VAT_rate']
            return ask('vat_rate','KDV oranını belirtmediniz; belgede yer alan KDV oranı nedir? Oranı doğrulamadan kayıt oluşturamam.')
        if taxable and (len(rates)!=1 or rates[0]<0 or rates[0]>100):
            return ask('single_vat_rate','Bu işlem için tek ve geçerli KDV oranını belirtin; farklı oranlı kalemler ayrı ele alınmalı.')
        if taxable and any(w in text for w in ('tevkifat','istisna','muaf','indirilemez','indirilemeyen','binek','otomobil')):
            state['knowledge_types']['current']=['VAT_deduction_or_special_treatment']
            return ask('verified_tax_treatment','Bu işlemde KDV indirimi/istisna/tevkifat koşulları doğrulanmalı. Belgedeki uygulama ve işletmenin kullanım amacı nedir? Otomatik 191 kaydı oluşturmuyorum.')
        cash=bool(re.search(r"\b(?:nakit|kasadan|kasaya|cash)\b",text))
        bank=bool(re.search(r"\b(?:banka\w*|havale\w*|eft)\b",text))
        deferred=bool(re.search(r"\b(?:vadeli|veresiye|odemedi\w*|odenmedi\w*)\b",text))
        if event!='cash_deposit':
            if cash and bank or deferred and (cash or bank or 'pesin' in text):
                return ask('conflicting_payment','Ödeme bilgileri çelişiyor. İşlem vadeli mi, nakit mi, banka üzerinden mi?')
            if not cash and not bank and not deferred:
                return ask('payment_method','Ödeme nakit mi banka üzerinden mi yapıldı?' if 'pesin' in text or not taxable else 'Alış vadeli mi, nakit mi, banka üzerinden mi ödendi?')
            if deferred and not taxable:
                return ask('payment_method','Borç/alacak kapatma işlemi gerçekleşti mi? Tahsilat/ödeme nakit mi banka üzerinden mi?')
        mode='nakit' if cash else 'banka' if bank else 'vadeli'
        state['known_facts']['payment']=mode if event!='cash_deposit' else 'cash_to_bank'
        included = 'kdv dahil' in text
        excluded = bool(re.search(r"kdv haric|matrah|\+\s*(?:kdv|%)", text))
        if taxable and (included == excluded):
            return ask('amount_basis','Verdiğiniz tutar KDV dahil toplam mı, KDV hariç matrah mı?')
        if event=='expense' and not ('7/a' in text and any(w in text for w in ('genel yonetim','yonetim gider','idari'))):
            return ask('expense_function','Giderin işletmedeki amacı ve maliyet yöntemi nedir (üretim, pazarlama, genel yönetim; 7/A veya 7/B)? Otomatik 770 seçemem.')
        state['principles']=self._accounting_principles()
        if not state['principles']:
            return ask('validated_principles','Yerel muhasebe ilkelerinin kaynağı doğrulanamadı; kayıt önerisini oluşturamıyorum.')
        try:
            tax=kdv(amount,rates[0],included='kdv dahil' in text) if taxable else None
            if taxable:
                state['known_facts'].update(vat_rate=str(rates[0]),net=str(tax['matrah']),vat=str(tax['kdv']),gross=str(tax['toplam']),rate_source='user_document_input')
                constructors={'purchase':purchase_goods,'asset_purchase':fixed_asset_purchase,'expense':expense_invoice}
                kwargs={'account':asset} if event=='asset_purchase' else {}
                entry=constructors[event](tax['matrah'],rates[0],mode=mode,**kwargs)
                # Use the original gross/net split: reverse VAT must not re-round the tax twice.
                for line in entry.lines:
                    if line.account=='191':line.debit=tax['kdv']
                    elif line.credit:line.credit=tax['toplam']
                if tax['matrah']+tax['kdv']!=tax['toplam']:raise JournalError('KDV + matrah toplamla eşleşmedi')
                if entry.total_debit!=tax['toplam']:raise JournalError('Kayıt toplamı belge toplamıyla eşleşmedi')
            else:
                entry={'cash_deposit':lambda:cash_deposit(amount),'customer_collection':lambda:collection(amount,mode),'vendor_payment':lambda:payment(amount,mode)}[event]()
            source='knowledge/muhasebe_kayit_sablonlari.json'
            reasons={'purchase':'Stok artar; ödeme hesabı veya satıcı borcu karşılık oluşturur.',
                     'asset_purchase':'İşletmede kullanılan sabit kıymet ilgili varlık hesabında izlenir.',
                     'expense':'Belirtilen 7/A genel yönetim gideri giderleştirilir.',
                     'cash_deposit':'Bankadaki varlık artar, kasadaki varlık azalır; gelir/gider veya mal alışı oluşmaz.',
                     'customer_collection':'Kasa/banka artar; daha önce doğmuş müşteri alacağı kapanır. Yeni satış veya KDV oluşmaz.',
                     'vendor_payment':'Satıcı borcu azalır; kasa/banka azalır. Yeni mal alışı veya KDV oluşmaz.'}
            for line in entry.lines:
                line.memo=reasons[event];line.source_reference=source
            entry.validate(self.chart)
            settlement = _SETTLEMENT[mode] or '320'
            expected = ({'purchase':({'153','191'},{settlement}),
                         'asset_purchase':({asset,'191'},{settlement}),
                         'expense':({'770','191'},{settlement})}[event] if taxable else
                        {'cash_deposit':({'102'},{'100'}),
                         'customer_collection':({_SETTLEMENT[mode]},{'120'}),
                         'vendor_payment':({'320'},{_SETTLEMENT[mode]})}[event])
            if any(line.account not in expected[0 if line.debit else 1] for line in entry.lines):
                raise JournalError('Hesap yönü işlem türü ve ödeme bilgisiyle uyuşmuyor')
            state.update(status='VALID',journal=entry.to_dict(self.chart),invariants={'balanced':True,'positive_money':True,'chart_accounts':True,'account_side_compatible':True,'vat_reconciled':True if taxable else None})
            explanation='OLAY: '+entry.description+'\nGEREKÇE: '+reasons[event]
            if taxable:explanation+='\nHESAP: '+format_tl(tax['matrah'])+' + '+format_tl(tax['kdv'])+' KDV = '+format_tl(tax['toplam'])
            explanation+='\n'+entry.render(self.chart)
            if state['assumptions']:explanation+='\nVARSAYIM: '+' '.join(state['assumptions'])
            explanation+='\nİLKELER: '+', '.join(p['name'] for p in state['principles'])
            explanation+='\nKAYNAK: '+source+'; config/tdhp.json'
            explanation+='\nNOT: Bu bir kayıt önerisidir; belge tarihi/numarası ve '+('KDV indirim koşulları ' if taxable else 'işlemin belgesi ')+'fiili kayıt öncesi kontrol edilmelidir.'
            return 'SONUÇ:\n'+explanation
        except (JournalError,CalculationError,ArithmeticError,ValueError) as exc:
            state.update(status='INVALID',invariant_failures=[str(exc)],journal=None)
            return 'Kaizen: Kayıt oluşturulamadı: '+str(exc)

    def _accounting_principles(self):
        from memory.principle_registry import PrincipleRegistry
        if self.principle_registry is not None:
            rows=[self.principle_registry.get(pid) for pid in ('borc_alacak','hesap_siniflandirma')]
        else:
            import json
            from learning.principle_seed import PRINCIPLES_SEED_PATH
            rows=[p for p in json.loads(PRINCIPLES_SEED_PATH.read_text(encoding='utf8')) if p['principle_id'] in ('borc_alacak','hesap_siniflandirma')]
        if len(rows)!=2 or any(not r or r.get('status','active')!='active' or not r.get('source') for r in rows):return []
        return [PrincipleRegistry.accounting_contract(r) for r in rows]
