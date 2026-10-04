"""KAIZEN Accountant Phase 4: kısmi / taksitli alacak tahsilatı (receivable collection).

Bu modül YENİ bir muhasebe/yevmiye motoru DEĞİLDİR. Var olan bir ticari alacağın
(120 Alıcılar) kısmen veya taksitle tahsil edilmesini, mevcut Phase-2/3 belge <-> yevmiye
mutabakat hattının (`accounting/document_reconciliation.py::reconcile_document_entry`)
ÜZERİNE ince bir alacak-pozisyonu katmanı olarak ekler:

  1) Belge ve yevmiye kaydı önce BİREBİR mevcut Phase-2/3 denetiminden geçer --
     dengesiz kayıt (INVALID_ENTRY), aritmetik bozuk belge (INVALID_DOCUMENT),
     tahsilatın 600/391 (yeni satış/KDV) satırlarıyla karıştırılması, kasa/banka
     çelişkisi ve ödeme şekli eksikliği hep mevcut kurallarla yakalanır; burada
     yeniden kurallanmaz.
  2) Katmanın kendi eklediği TEK şey alacak pozisyonu aritmetiğidir:
     kalan = açık alacak bakiyesi - tahsil edilen tutar.
       * tahsilat < bakiye  -> kısmi tahsilat (partial), kalan > 0
       * tahsilat = bakiye  -> tam tahsilat (full), kalan = 0
       * tahsilat > bakiye  -> MISMATCH: fazla tahsilat sessizce normal tahsilat
         sayılmaz; ne fazlası için gelir yazılır ne de tutar "düzeltilir".
       * bakiye bilinmiyorsa kısmi/tam ayrımı ve fazla-tahsilat denetimi YAPILAMAZ
         -> INSUFFICIENT_INFORMATION (bakiye uydurulmaz).
       * tahsilat tutarı belgelenmemişse -> INSUFFICIENT_INFORMATION (tutar
         uydurulmaz).
  3) Birden fazla taksit ayrı birer tahsilat olayıdır: her taksit kendi çağrısıyla,
     bir önceki çağrının bildirdiği kalan bakiye üzerinden doğrulanır. Modül
     durum tutmaz (stateless) -- defter/ledger tutmak bu katmanın işi değildir.

Tahsilat sırasında satış hasılatı (600) veya KDV (391) asla yeniden kaydedilmez;
bu garanti doğrudan Phase-3'ün `_is_receivable_collection_document` denetiminden mirastır.

Para her yerde Decimal'dir; binary float asla para kabul edilmez ve eksik tutar/bakiye
asla uydurulmaz.

Author: Kaizen-1 Accountant Phase 4 - receivable collection reconciliation.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from accounting.calculators import money as _quantize_money
from accounting.document_reconciliation import (
    NormalizedDocument,
    ReconciliationResult,
    reconcile_document_entry,
)

ZERO = Decimal("0.00")

_MISSING_OUTSTANDING_CLARIFICATION = (
    "Açık alacak bakiyesi nedir? Kısmi/tam ayrımı ve fazla-tahsilat denetimi "
    "için açık bakiye bilinmelidir; bakiye uydurulmadı."
)
_MISSING_COLLECTED_CLARIFICATION = (
    "Tahsilat tutarı nedir? Belgede/bildirimde tahsil edilen tutar yok; tutar uydurulmadı."
)


class ReceivableCollectionResult(ReconciliationResult):
    """Phase-4 sonucu: Phase-2/3 ReconciliationResult + alacak pozisyonu alanları.

    Ek alanlar her zaman ya kesin Decimal ya da None'dır (None = belirlenemedi/belirtilmedi):
      - collection_type: 'partial' | 'full' | None
      - payment_account: '100' | '102' | None          (yevmiyedeki gerçek tahsilat hesabı)
      - collected_amount: Decimal | None               (belgedeki tahsilat tutarı)
      - outstanding_receivable: Decimal | None          (çağrıya verilen açık bakiye)
      - remaining_receivable: Decimal | None            (bakiye - tahsilat; yalnız her ikisi
                                                         de biliniyorsa hesaplanır)
    """

    def __init__(
        self,
        *args: Any,
        collection_type: Optional[str] = None,
        payment_account: Optional[str] = None,
        collected_amount: Optional[Decimal] = None,
        outstanding_receivable: Optional[Decimal] = None,
        remaining_receivable: Optional[Decimal] = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.collection_type = collection_type
        self.payment_account = payment_account
        self.collected_amount = collected_amount
        self.outstanding_receivable = outstanding_receivable
        self.remaining_receivable = remaining_receivable

    def __str__(self) -> str:
        lines = [super().__str__()]
        if self.collection_type is not None:
            lines.append(f"Tahsilat türü: {self.collection_type}")
        if self.payment_account is not None:
            lines.append(f"Tahsilat hesabı: {self.payment_account}")
        if self.collected_amount is not None:
            lines.append(f"Tahsil edilen: {self.collected_amount}")
        if self.remaining_receivable is not None:
            lines.append(f"Kalan alacak: {self.remaining_receivable}")
        return "\n".join(lines)


def _to_decimal(value: Any) -> Optional[Decimal]:
    """int/str/Decimal -> Decimal; float/binary ya da çevrilemez girdi -> None.

    Asla bir tutar/bakiye uydurulmaz: belirsiz girdi None olarak kalır."""
    return NormalizedDocument._to_decimal(value)


def _collection_payment_account(journal_entry: Dict[str, Any]) -> Optional[str]:
    """Yevmiyedeki tahsilat hesabını (100 Kasa / 102 Bankalar, borç tarafı) OKUR.

    Hesap seçimi yapılmaz; yalnızca verilen kayıttaki mevcut satır okunur. Birden
    fazla ya da sıfır kasa/banka borç satırı varsa hesap belirsizdir -> None."""
    accounts = set()
    for line in journal_entry.get("lines") or []:
        code = str(line.get("account_code", ""))
        if code not in ("100", "102"):
            continue
        try:
            debit = Decimal(str(line.get("debit") or "0"))
        except (InvalidOperation, TypeError):
            return None
        if debit > ZERO:
            accounts.add(code)
    if len(accounts) != 1:
        return None
    return next(iter(accounts))


def reconcile_receivable_collection(
    document: NormalizedDocument,
    journal_entry: Any,
    outstanding_receivable: Any = None,
    trace: Optional[Any] = None,
) -> ReceivableCollectionResult:
    """Mevcut bir ticari alacağın (kısmi/taksitli/tam) tahsilatını doğrular.

    `document`: NormalizedDocument -- tahsilat belgesi. Phase-3 sözleşmesi gereği
    `document_type` 'tahsilat'/'collection' içerir ve tahsilat TUTARI `net_amount`
    alanında taşınır (bir tahsilatta net/KDV/brüt ayrımı yoktur).
    `journal_entry`: tahsilat için oluşturulmuş/önerilmiş VAR OLAN yevmiye kaydı
    (gerçek `accounting.journal.JournalEntry` ya da `.to_dict()` çıktısı).
    `outstanding_receivable`: tahsilat ÖNCESİ açık alacak bakiyesi (Decimal/int/str).
    Bilinmiyorsa None verilir -- bu durumda kısmi/tam ayrımı ve fazla-tahsilat
    denetimi yapılamaz ve sonuç INSUFFICIENT_INFORMATION olur; bakiye uydurulmaz.

    Döndürülen ReceivableCollectionResult Trace'e de işlenir (düz attribute
    ataması -- KaizenTrace'in mevcut Phase-2/3 deseni).
    """
    if hasattr(journal_entry, "to_dict"):
        journal_entry = journal_entry.to_dict()

    outstanding = _to_decimal(outstanding_receivable)
    collected = document.net_amount  # Phase-3 sözleşmesi: tahsilat tutarı net_amount'ta
    # Kanonik para temsili: Phase-1 `accounting/calculators.py::money` ile BİREBİR aynı
    # kural (quantize 0.01, ROUND_HALF_UP -- kurus hassasiyeti invarianti). Deger daha
    # once kuantize edilmemisse (orn. belgeden dogrudan gelen Decimal("5000")) burada
    # ayni kanonik forma getirilir; degerin kendisi degistirilmez/duzeltilmez, yalnizca
    # para temsili normalize edilir.
    if outstanding is not None:
        outstanding = _quantize_money(outstanding)
    if collected is not None:
        collected = _quantize_money(collected)

    payment_account = _collection_payment_account(journal_entry)

    def _finish(status, *, discrepancies=None, missing=None, summary=None,
                document_checks=None, entry_checks=None, collection_type=None,
                remaining=None):
        result = ReceivableCollectionResult(
            status=status,
            discrepancies=discrepancies,
            missing_information=missing,
            document_checks=document_checks,
            entry_checks=entry_checks,
            reasoning_summary=summary,
            collection_type=collection_type,
            payment_account=payment_account,
            collected_amount=collected,
            outstanding_receivable=outstanding,
            remaining_receivable=remaining,
        )
        _record_collection_trace(trace, result, document_checks, entry_checks)
        return result

    # --- Adım 1: mevcut Phase-2/3 belge <-> yevmiye denetimi, AYNEN ----------------
    # Dengesiz kayıt, aritmetik bozuk belge, tahsilata karışan 600/391 satırları,
    # kasa/banka çelişkisi ve eksik ödeme şekli burada, mevcut kurallarla yakalanır.
    # trace'e ASLA None dışında geçilmez: Trace kaydı bu modülün kendi _finish
    # noktasında tek kez yapılır (çift kayıt yok).
    base = reconcile_document_entry(document, journal_entry, trace=None)
    if base.status != ReconciliationResult.MATCH:
        return _finish(
            base.status,
            discrepancies=base.discrepancies,
            missing=base.missing_information,
            summary=base.reasoning_summary,
            document_checks=base.document_checks,
            entry_checks=base.entry_checks,
        )

    document_checks = dict(base.document_checks)
    entry_checks = dict(base.entry_checks)
    document_checks.update({"outstanding_known": outstanding is not None,
                            "collected_known": collected is not None})

    # --- Adım 2: tahsilat tutarı bilinmeden pozisyon kurulamaz ----------------------
    if collected is None:
        return _finish(
            ReconciliationResult.INSUFFICIENT_INFORMATION,
            missing=[_MISSING_COLLECTED_CLARIFICATION],
            summary="Tahsilat tutarı belirtilmemiş; tutar uydurulmadı.",
            document_checks=document_checks, entry_checks=entry_checks,
        )

    # --- Adım 3: açık bakiye bilinmeden kısmi/tam ayrımı yapılamaz ------------------
    if outstanding is None:
        return _finish(
            ReconciliationResult.INSUFFICIENT_INFORMATION,
            missing=[_MISSING_OUTSTANDING_CLARIFICATION],
            summary="Açık alacak bakiyesi belirtilmeden kısmi/tam ayrımı ve fazla-tahsilat "
                    "denetimi yapılamaz; bakiye uydurulmadı.",
            document_checks=document_checks, entry_checks=entry_checks,
        )

    # --- Adım 4: alacak pozisyonu aritmetiği ---------------------------------------
    if collected > outstanding:
        return _finish(
            ReconciliationResult.MISMATCH,
            discrepancies=[
                f"Tahsilat tutarı ({collected}) açık alacak bakiyesini ({outstanding}) aşıyor; "
                f"fazla tahsilat sessizce normal tahsilat sayılmaz, gelir/KDV de oluşturulmaz"
            ],
            summary="Tahsilat açık bakiyeyi aşıyor.",
            document_checks=document_checks, entry_checks=entry_checks,
        )

    remaining = outstanding - collected
    collection_type = "full" if remaining == ZERO else "partial"
    return _finish(
        ReconciliationResult.MATCH,
        summary=(
            "Tahsilat açık alacakla tutarlı; "
            + ("alacak tamamen kapandı." if collection_type == "full"
               else f"kısmi tahsilat; kalan alacak {remaining}.")
        ),
        document_checks=document_checks, entry_checks=entry_checks,
        collection_type=collection_type,
        remaining=remaining,
    )


def _record_collection_trace(trace, result: ReceivableCollectionResult,
                             document_checks, entry_checks) -> None:
    """Phase-4 trace kaydı. Phase-2/3 ile aynı düz-attribute deseni + ek
    `collection_details` alanı (olay türü, partial/full, tahsilat hesabı, tutar,
    kalan, durum). Gizli veri ya da ham belge içeriği Trace'e konmaz."""
    if trace is None:
        return
    trace.document_validation = {"document_checks": document_checks,
                                 "entry_checks": entry_checks}
    trace.reconciliation_status = result.status
    trace.discrepancies = list(result.discrepancies)
    trace.missing_information = list(result.missing_information)
    trace.collection_details = {
        "event_type": "receivable_collection",
        "collection_type": result.collection_type,
        "payment_account": result.payment_account,
        "collected_amount": (str(result.collected_amount)
                             if result.collected_amount is not None else None),
        "remaining_receivable": (str(result.remaining_receivable)
                                 if result.remaining_receivable is not None else None),
        "reconciliation_status": result.status,
    }
