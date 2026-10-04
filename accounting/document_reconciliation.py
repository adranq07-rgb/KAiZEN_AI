"""KAIZEN Accounting Document - Journal Reconciliation (Phase 2 + Phase 3).

Compares normalized document facts against an EXISTING (already booked / proposed)
journal entry, expressed in the real Phase-1 `accounting.journal.JournalEntry.to_dict()`
shape. Determines MATCH / MISMATCH / INSUFFICIENT_INFORMATION / INVALID_DOCUMENT /
INVALID_ENTRY.

Bu modül YENİ bir muhasebe/hesap seçim motoru DEĞİLDİR. Hesap kodu anlamları (153 Ticari
Mallar, 191 İndirilecek KDV, 320 Satıcılar, 100 Kasa, 102 Bankalar, 391 Hesaplanan KDV, 600
Yurt İçi Satışlar, 120 Alıcılar) mevcut Tek Düzen Hesap Planı'ndan (accounting/journal.py,
accounting/chart_of_accounts.py) aynen okunur; burada yeniden seçilmez/üretilmez. Reconciliation
yalnızca VERİLEN (başka bir yerde zaten oluşturulmuş) bir yevmiye kaydının, VERİLEN belge
gerçekleriyle tutarlı olup olmadığını denetler -- "dengeli ama yanlış" bir kayıt da MISMATCH
olarak yakalanır (bkz. aşağıdaki worked example).

Faz 3 (satış/alacak tarafı): aynı mimari, simetrik olarak genişletildi.
- Kredili/veresiye satış, peşin (nakit/banka) satış ve mevcut bir alacağın tahsilatı
  birbirinden ayırt edilir. Bir tahsilat ASLA yeni bir satış/KDV satırı (600/391) ile
  karıştırılmaz -- bu kasıtlı bir ayrımdır (bkz. _is_receivable_collection_document).
- Ödeme şekli çelişki denetimi simetriktir: 100/102 yerine 320 (satıcı) ya da 120 (alıcı)
  beklenebilir; hangisi beklendiği, kayıttaki mevcut gelir (600) / maliyet (153) satırından
  anlaşılır -- ayrı bir yön parametresi İCAT edilmedi.

Money MUST use Decimal. Never invent missing values (ör. eksik KDV oranını asla varsaymaz).

Author: Kaizen-1 Accountant Phase 2/3 - document <-> journal reconciliation.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from core.text_tr import fold_tr

ZERO = Decimal("0.00")

# Hesap planı anlamları (yalnızca OKUNUR; burada hesap seçilmez) -----------------------------
_VAT_ACCOUNTS = {"191", "391"}            # İndirilecek KDV (alış) / Hesaplanan KDV (satış)
_SETTLEMENT_ACCOUNTS = {"100", "102", "320", "120"}  # Kasa / Bankalar / Satıcılar / Alıcılar
_REVENUE_ACCOUNTS = {"600"}                # Yurt İçi Satışlar (mevcut accounting/journal.py::sale_goods)
_COST_ACCOUNTS = {"153"}                   # Ticari Mallar (mevcut accounting/journal.py::purchase_goods)

_CASH_WORDS = ("nakit", "pesin", "kasadan", "kasaya", "cash")
_BANK_WORDS = ("banka", "havale", "eft", "bank")
_CREDIT_WORDS = ("vadeli", "veresiye", "credit", "borc", "satici", "vendor", "tedarikci", "alici")
_COLLECTION_WORDS = ("tahsilat", "collection")

_MISSING_VAT_CLARIFICATION = "KDV oranı veya KDV tutarı nedir?"


def _normalize_payment_method(raw: Optional[str]) -> Optional[str]:
    """Belgedeki ödeme şeklini 'cash' / 'bank' / 'credit' kanonik etiketine indirger.

    Bilinmeyen/boş girdide None döner -- asla tahmin yapılmaz."""
    if not raw:
        return None
    text = fold_tr(str(raw))
    if any(w in text for w in _CASH_WORDS):
        return "cash"
    if any(w in text for w in _BANK_WORDS):
        return "bank"
    if any(w in text for w in _CREDIT_WORDS):
        return "credit"
    return None


def _is_receivable_collection_document(document: "NormalizedDocument") -> bool:
    """Belge, mevcut bir alacağın tahsilatını mı tanımlıyor (yeni bir satış DEĞİL)?

    Yalnızca document_type'taki açık işaretle belirlenir -- asla tahmin edilmez.
    Bir tahsilatta net_amount alanı "tahsil edilen tutar" anlamında yeniden kullanılır;
    vat_rate/vat_amount/gross_amount/line_items uygulanamaz (None kalmalı)."""
    if not document.document_type:
        return False
    text = fold_tr(str(document.document_type))
    return any(w in text for w in _COLLECTION_WORDS)


# ------------------------------------------------------------------
# Normalized Document Representation
# ------------------------------------------------------------------

class NormalizedDocument:
    """Production document facts extracted/structured for reconciliation.

    All monetary values are Decimal or None (unknown). Unknown is valid;
    never invent a value.
    """

    __slots__ = (
        "document_type",
        "document_number",
        "document_date",
        "counterparty",
        "payment_method",
        "net_amount",       # Decimal or None
        "vat_rate",         # Decimal or str or None
        "vat_amount",       # Decimal or None
        "gross_amount",     # Decimal or None
        "line_items",       # List[Decimal] or None
        "source_reference", # str or None
    )

    def __init__(
        self,
        document_type: Optional[str] = None,
        document_number: Optional[str] = None,
        document_date: Optional[str] = None,
        counterparty: Optional[str] = None,
        payment_method: Optional[str] = None,
        net_amount: Optional[Decimal] = None,
        vat_rate: Optional[Any] = None,  # Decimal or str or None
        vat_amount: Optional[Decimal] = None,
        gross_amount: Optional[Decimal] = None,
        line_items: Optional[List[Decimal]] = None,
        source_reference: Optional[str] = None,
    ):
        self.document_type = document_type
        self.document_number = document_number
        self.document_date = document_date
        self.counterparty = counterparty
        self.payment_method = payment_method
        self.net_amount = net_amount
        self.vat_rate = vat_rate
        self.vat_amount = vat_amount
        self.gross_amount = gross_amount
        self.line_items = line_items
        self.source_reference = source_reference

    @staticmethod
    def _to_decimal(value: Any) -> Optional[Decimal]:
        """Convert int/str/Decimal to Decimal; return None if impossible."""
        if value is None or value is False:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            # Never silently accept a binary float as money.
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def gross_invariant_holds(self) -> Optional[bool]:
        """Return None if insufficient data; True if net+vat==gross; False if mismatch."""
        if self.net_amount is None or self.vat_amount is None or self.gross_amount is None:
            return None
        return self.net_amount + self.vat_amount == self.gross_amount

    def line_total_reconciles(self) -> Optional[bool]:
        """Return None if insufficient data; True if sum(lines) == net; False if mismatch."""
        if self.net_amount is None or self.line_items is None:
            return None
        try:
            total = sum(self.line_items, ZERO)
            return total == self.net_amount
        except (TypeError, ArithmeticError):
            return None

    def vat_known(self) -> bool:
        """Belgede KDV oranı VEYA KDV tutarı belirtilmiş mi (ikisi de yoksa asla varsayılmaz)."""
        return self.vat_rate is not None or self.vat_amount is not None


class ReconciliationResult:
    """Structured reconciliation outcome."""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    INVALID_DOCUMENT = "INVALID_DOCUMENT"
    INVALID_ENTRY = "INVALID_ENTRY"

    def __init__(
        self,
        status: str,
        discrepancies: Optional[List[str]] = None,
        missing_information: Optional[List[str]] = None,
        document_checks: Optional[Dict[str, Any]] = None,
        entry_checks: Optional[Dict[str, Any]] = None,
        reasoning_summary: Optional[str] = None,
    ):
        self.status = status
        self.discrepancies = discrepancies or []
        self.missing_information = missing_information or []
        self.document_checks = document_checks or {}
        self.entry_checks = entry_checks or {}
        self.reasoning_summary = reasoning_summary

    def __str__(self) -> str:
        lines = [f"Status: {self.status}"]
        if self.discrepancies:
            lines.append("Discrepancies:")
            for d in self.discrepancies:
                lines.append(f"  - {d}")
        if self.missing_information:
            lines.append("Missing information:")
            for m in self.missing_information:
                lines.append(f"  - {m}")
        if self.reasoning_summary:
            lines.append(f"Reasoning: {self.reasoning_summary}")
        return "\n".join(lines)


def _journal_facts(journal_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Derive comparison facts from the REAL Phase-1 `JournalEntry.to_dict()` shape.

    Reuses existing account codes/labels as-is; never re-selects an account."""
    lines = journal_entry.get("lines") or []
    vat_amount = ZERO
    settlement_codes: List[str] = []
    settlement_labels: List[str] = []
    codes: List[str] = []
    for line in lines:
        code = str(line.get("account_code", ""))
        codes.append(code)
        try:
            debit = Decimal(str(line.get("debit") or "0"))
            credit = Decimal(str(line.get("credit") or "0"))
        except (InvalidOperation, TypeError):
            continue
        amount = debit if debit else credit
        if code in _VAT_ACCOUNTS:
            vat_amount += amount
        if code in _SETTLEMENT_ACCOUNTS:
            settlement_codes.append(code)
            settlement_labels.append(f"{code} {line.get('account_name', '')}".strip())

    def _dec(value):
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError):
            return None

    debit_total = _dec(journal_entry.get("debit_total"))
    credit_total = _dec(journal_entry.get("credit_total"))
    balanced = debit_total is not None and credit_total is not None and debit_total == credit_total
    total = None
    if debit_total is not None and credit_total is not None:
        total = debit_total if debit_total >= credit_total else credit_total
    net_amount = (total - vat_amount) if total is not None else None

    distinct_settlement = sorted(set(settlement_codes))
    settlement_code = settlement_codes[0] if len(distinct_settlement) == 1 else None
    settlement_label = settlement_labels[0] if len(distinct_settlement) == 1 else None

    has_revenue = any(c in _REVENUE_ACCOUNTS for c in codes)
    has_cost = any(c in _COST_ACCOUNTS for c in codes)
    has_vat_line = vat_amount != ZERO or any(c in _VAT_ACCOUNTS for c in codes)

    return {
        "codes": codes,
        "vat_amount": vat_amount,
        "gross_amount": total,
        "net_amount": net_amount,
        "debit_total": debit_total,
        "credit_total": credit_total,
        "balanced": balanced,
        "settlement_account": settlement_code,
        "settlement_label": settlement_label,
        "distinct_settlement_accounts": distinct_settlement,
        "has_revenue": has_revenue,
        "has_cost": has_cost,
        "has_vat_line": has_vat_line,
    }


def reconcile_document_entry(
    document: NormalizedDocument,
    journal_entry: Dict[str, Any],
    trace: Optional[Any] = None,
) -> ReconciliationResult:
    """Compare a NormalizedDocument against an existing canonical journal entry.

    `journal_entry` MUST be the real Phase-1 representation: either a
    `accounting.journal.JournalEntry` instance (its `.to_dict()` is used), or
    the dict that `.to_dict()` already produces. No parallel journal engine.

    Returns a ReconciliationResult. If `trace` is given (a `core.trace.KaizenTrace`
    instance), the minimal Phase-2/3 trace fields are set directly on it (plain
    attribute assignment -- KaizenTrace has no methods of its own, by design).
    """
    if hasattr(journal_entry, "to_dict"):
        journal_entry = journal_entry.to_dict()

    discrepancies: List[str] = []
    missing_information: List[str] = []
    is_collection = _is_receivable_collection_document(document)

    # --- Step 1: document's own internal arithmetic (INVALID_DOCUMENT) -----------------
    # For a receivable collection, net/VAT/gross do not apply (net_amount holds the
    # collected amount instead) -- both checks naturally return None (not False) since
    # vat_amount/gross_amount stay unset, so this step is already safe unchanged.
    gi = document.gross_invariant_holds()
    lt = document.line_total_reconciles()
    document_checks = {
        "gross_invariant_holds": gi,
        "line_total_reconciles": lt,
        "vat_known": document.vat_known(),
        "is_receivable_collection": is_collection,
    }
    document_invalid = gi is False or lt is False
    if document_invalid:
        if gi is False:
            discrepancies.append(
                f"Belge aritmetiği: net ({document.net_amount}) + KDV ({document.vat_amount}) "
                f"!= brüt ({document.gross_amount})"
            )
        if lt is False:
            discrepancies.append(
                f"Belge kalem toplamları ({document.line_items}) net tutarla ({document.net_amount}) uyuşmuyor"
            )
        result = ReconciliationResult(
            status=ReconciliationResult.INVALID_DOCUMENT,
            discrepancies=discrepancies,
            document_checks=document_checks,
            reasoning_summary="Belge kendi içinde aritmetik olarak geçersiz; tutar sessizce düzeltilmedi.",
        )
        _record_trace(trace, document, result, document_checks, {})
        return result

    # --- Step 2: the journal entry's own validity (INVALID_ENTRY) -----------------------
    jf = _journal_facts(journal_entry)
    entry_checks = {"balanced": jf["balanced"]}
    if jf["debit_total"] is not None and jf["credit_total"] is not None and not jf["balanced"]:
        result = ReconciliationResult(
            status=ReconciliationResult.INVALID_ENTRY,
            discrepancies=[
                f"Yevmiye kaydı dengede değil: borç={jf['debit_total']}, alacak={jf['credit_total']}"
            ],
            document_checks=document_checks,
            entry_checks=entry_checks,
            reasoning_summary="Kayıt borç=alacak şartını sağlamıyor.",
        )
        _record_trace(trace, document, result, document_checks, entry_checks)
        return result

    # --- Step 3: missing VAT info on the document (INSUFFICIENT_INFORMATION) -----------
    # Does not apply to a pure receivable collection -- there is no net/VAT split there.
    if not is_collection and not document.vat_known():
        missing_information.append(_MISSING_VAT_CLARIFICATION)
        result = ReconciliationResult(
            status=ReconciliationResult.INSUFFICIENT_INFORMATION,
            missing_information=missing_information,
            document_checks=document_checks,
            entry_checks=entry_checks,
            reasoning_summary="KDV oranı/tutarı belirtilmeden karşılaştırma yapılamaz; oran uydurulmadı.",
        )
        _record_trace(trace, document, result, document_checks, entry_checks)
        return result

    doc_payment = _normalize_payment_method(document.payment_method)
    settlement_account = None

    if is_collection:
        # --- Step 4 (collection path): a collection is NOT a new sale. ------------------
        if jf["has_revenue"] or jf["has_cost"] or jf["has_vat_line"]:
            discrepancies.append(
                "Bu mevcut bir alacağın tahsilatıdır; tahsilat için yeni satış/KDV satırı "
                "(600/391) oluşturulmamalı"
            )
        if "120" not in jf["codes"]:
            discrepancies.append("Beklenen 120 Alıcılar satırı tahsilat kaydında yok")
        cash_bank_codes = [c for c in jf["codes"] if c in ("100", "102")]
        distinct_cash_bank = sorted(set(cash_bank_codes))
        if len(distinct_cash_bank) == 1:
            collected_via = distinct_cash_bank[0]
            if doc_payment == "bank" and collected_via == "100":
                discrepancies.append(
                    "Ödeme şekli uyuşmazlığı: belge banka tahsilatı diyor ama kayıt 100 Kasa ile yapılmış"
                )
            elif doc_payment == "cash" and collected_via == "102":
                discrepancies.append(
                    "Ödeme şekli uyuşmazlığı: belge nakit tahsilat diyor ama kayıt 102 Bankalar ile yapılmış"
                )
        elif doc_payment is not None and not cash_bank_codes:
            discrepancies.append("Tahsilat kaydında kasa/banka satırı yok")
        if document.net_amount is not None and jf["gross_amount"] is not None:
            if document.net_amount != jf["gross_amount"]:
                discrepancies.append(
                    f"Tahsilat tutarı uyuşmazlığı: belge {document.net_amount}, kayıt {jf['gross_amount']}"
                )
    else:
        # --- Step 4 (sale/purchase path): cross document <-> entry comparison ----------
        if document.vat_amount is not None and jf["vat_amount"] is not None:
            if document.vat_amount != jf["vat_amount"]:
                discrepancies.append(
                    f"KDV uyuşmazlığı: belge KDV={document.vat_amount}, kayıt KDV={jf['vat_amount']}"
                )

        if document.net_amount is not None and jf["net_amount"] is not None:
            if document.net_amount != jf["net_amount"]:
                discrepancies.append(
                    f"Net tutar uyuşmazlığı: belge net={document.net_amount}, kayıt net={jf['net_amount']}"
                )

        if document.gross_amount is not None and jf["gross_amount"] is not None:
            if document.gross_amount != jf["gross_amount"]:
                discrepancies.append(
                    f"Brüt/karşı değer uyuşmazlığı: belge brüt={document.gross_amount}, "
                    f"kayıt toplamı={jf['gross_amount']}"
                )

        # Expected-vs-unexpected VAT/revenue component. In this account model, VAT and
        # the revenue/cost line always travel together on one entry, so the single VAT
        # signal below also covers "missing expected revenue component" without a
        # separate, redundant check.
        doc_expects_vat = document.vat_amount is not None and document.vat_amount != ZERO
        doc_expects_no_vat = document.vat_amount is not None and document.vat_amount == ZERO
        entry_has_vat = jf["vat_amount"] != ZERO
        if doc_expects_vat and not entry_has_vat:
            discrepancies.append(
                "Beklenen KDV satırı kayıtta yok (belge KDV öngörüyor, kayıtta KDV tutarı sıfır)"
            )
        elif doc_expects_no_vat and entry_has_vat:
            discrepancies.append("Kayıtta beklenmeyen bir KDV satırı var (belge KDV öngörmüyor)")

        # Payment-method semantics: reuse existing Phase-1 account meanings. Symmetric
        # for purchase (100/102/320) and sale (100/102/120) -- which counterparty
        # account ("satıcı borcu"/320 vs "alıcı borcu"/120) is expected is read off the
        # entry's own revenue(600)/cost(153) line, never a separately invented direction flag.
        settlement_account = jf["settlement_account"]
        settlement_label = jf["settlement_label"] or settlement_account
        if doc_payment and settlement_account:
            if doc_payment == "bank" and settlement_account == "100":
                discrepancies.append(
                    f"Ödeme şekli uyuşmazlığı: belge banka ödemesi/tahsilatı diyor ama kayıt "
                    f"{settlement_label} (Kasa) ile kapatılmış"
                )
            elif doc_payment == "cash" and settlement_account == "102":
                discrepancies.append(
                    f"Ödeme şekli uyuşmazlığı: belge nakit ödeme/tahsilat diyor ama kayıt "
                    f"{settlement_label} (Bankalar) ile kapatılmış"
                )
            elif doc_payment == "credit" and settlement_account in ("100", "102"):
                if jf["has_revenue"]:
                    discrepancies.append(
                        f"Ödeme şekli uyuşmazlığı: belge vadeli/veresiye satış diyor (alıcı borcu/120 "
                        f"doğmalı) ama kayıt {settlement_label} ile peşin kapatılmış"
                    )
                else:
                    discrepancies.append(
                        f"Ödeme şekli uyuşmazlığı: belge vadeli/kredili alış diyor (satıcı borcu/320 "
                        f"doğmalı) ama kayıt {settlement_label} ile peşin kapatılmış"
                    )
            elif doc_payment in ("cash", "bank") and settlement_account == "120":
                discrepancies.append(
                    f"Ödeme şekli uyuşmazlığı: belge peşin (nakit/banka) tahsilat diyor ama kayıtta "
                    f"hâlâ 120 Alıcılar (tahsil edilmemiş alacak) görünüyor"
                )

    if discrepancies:
        result = ReconciliationResult(
            status=ReconciliationResult.MISMATCH,
            discrepancies=discrepancies,
            document_checks=document_checks,
            entry_checks=entry_checks,
            reasoning_summary=f"{len(discrepancies)} uyuşmazlık bulundu.",
        )
        _record_trace(trace, document, result, document_checks, entry_checks)
        return result

    # --- Step 5: still not enough to conclude MATCH? ------------------------------------
    unresolved = []
    if not is_collection:
        if gi is None:
            unresolved.append("Belge net+KDV+brüt üçlüsünden biri eksik")
        if document.gross_amount is None and jf["gross_amount"] is not None:
            unresolved.append("Belgede brüt/karşı değer tutarı belirtilmemiş")
    if doc_payment is None and (settlement_account is not None or is_collection):
        unresolved.append("Belgede ödeme şekli belirtilmemiş")
    if unresolved:
        result = ReconciliationResult(
            status=ReconciliationResult.INSUFFICIENT_INFORMATION,
            missing_information=unresolved,
            document_checks=document_checks,
            entry_checks=entry_checks,
            reasoning_summary="Karşılaştırma için yeterli belge bilgisi yok; hiçbir tutar uydurulmadı.",
        )
        _record_trace(trace, document, result, document_checks, entry_checks)
        return result

    result = ReconciliationResult(
        status=ReconciliationResult.MATCH,
        document_checks=document_checks,
        entry_checks=entry_checks,
        reasoning_summary="Belge ve yevmiye kaydı tutarlı.",
    )
    _record_trace(trace, document, result, document_checks, entry_checks)
    return result


def _record_trace(trace, document, result: ReconciliationResult, document_checks, entry_checks) -> None:
    """Minimal Phase-2/3 trace exposure. `KaizenTrace` is a plain dataclass (no methods
    of its own besides `to_dict`) -- every other call site in this codebase sets its
    fields by direct attribute assignment, so reconciliation follows the same pattern
    rather than inventing a `record_reconciliation()` method on the trace object."""
    if trace is None:
        return
    trace.document_validation = {"document_checks": document_checks, "entry_checks": entry_checks}
    trace.reconciliation_status = result.status
    trace.discrepancies = list(result.discrepancies)
    trace.missing_information = list(result.missing_information)


def document_from_raw(
    document_type: Optional[str] = None,
    document_number: Optional[str] = None,
    document_date: Optional[str] = None,
    counterparty: Optional[str] = None,
    payment_method: Optional[str] = None,
    net: Optional[str] = None,
    vat_rate: Optional[str] = None,
    vat_amount: Optional[str] = None,
    gross: Optional[str] = None,
    line_items: Optional[List[str]] = None,
    source_reference: Optional[str] = None,
) -> NormalizedDocument:
    """Build a NormalizedDocument from raw string/number inputs.

    All monetary values are converted via Decimal; unknown/empty -> None. For a
    receivable collection document (document_type containing "tahsilat"/"collection"),
    pass the collected amount via `net`; leave vat_rate/vat_amount/gross/line_items unset.
    """

    def _d(v: Optional[str]) -> Optional[Decimal]:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        if isinstance(v, float):
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None

    lines: Optional[List[Decimal]] = None
    if line_items:
        lines = [_d(l) for l in line_items if _d(l) is not None]

    return NormalizedDocument(
        document_type=document_type,
        document_number=document_number,
        document_date=document_date,
        counterparty=counterparty,
        payment_method=payment_method,
        net_amount=_d(net),
        vat_rate=vat_rate,
        vat_amount=_d(vat_amount),
        gross_amount=_d(gross),
        line_items=lines,
        source_reference=source_reference,
    )
