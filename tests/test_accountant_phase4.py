"""Accountant Phase 4: kismi / taksitli alacak tahsilati (receivable collection).

Mevcut bir ticari alacagin (120 Alicilar) kismen veya taksitler halinde tahsilinin
dogrulanmasi. Yeni motor yok: `reconcile_receivable_collection` iceriden mevcut
Phase-2/3 `reconcile_document_entry` denetimini calistirir; uretim girisi de
`KaizenBrain.reconcile_collection` / `KaizenEngine.reconcile_collection` (Phase-2/3
deseninin aynisi, cevap_ver zincirinin disinda).

FOCUSED testler (A-J) reconcile_receivable_collection'i gercek Phase-1 JournalEntry
nesneleri/dict'leriyle dogrudan cagirir. RUNTIME testleri gercek uretim yolunu
(KaizenEngine.reconcile_collection) kullanir; Phase-1/2/3 korunma kontrolleri ektir.
"""
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from config.config_manager import ConfigManager
from core.engine import KaizenEngine
from core.ai.offline_provider import OfflineProvider
from tests.doubles import NullExperienceMemory

from accounting.journal import JournalEntry
from accounting.document_reconciliation import ReconciliationResult, document_from_raw
from accounting.receivable_collection import (
    ReceivableCollectionResult,
    reconcile_receivable_collection,
)


@contextmanager
def engine():
    with TemporaryDirectory() as tmp:
        c = ConfigManager()
        c.config['retrieval']['hybrid_enabled'] = False
        c.config['research']['research_engine_enabled'] = False
        e = KaizenEngine(data_dir=Path(tmp) / 'data', log_dir=Path(tmp) / 'logs',
                          config=c, provider=OfflineProvider(), experience_memory=NullExperienceMemory())
        try:
            yield e
        finally:
            e.shutdown()


def _collection_doc(amount=None, payment_method=None):
    return document_from_raw(
        document_type="tahsilat", document_number="TAH-2026-0001",
        document_date="2026-10-01", counterparty="Örnek Müşteri A.Ş.",
        payment_method=payment_method, net=amount,
    )


def _collection_entry(cash_or_bank_account, amount, description="tahsilat"):
    return (JournalEntry(description)
            .debit(cash_or_bank_account, amount)
            .credit("120", amount))


def _sale_entry(receivable_or_cash_account, amount, net, vat, description="satis"):
    return (JournalEntry(description)
            .debit(receivable_or_cash_account, amount)
            .credit("600", net)
            .credit("391", vat))


# ------------------------------------------------------------------ FOCUSED A-J -----

def test_phase4_a_partial_bank_collection_match():
    """A) Bankadan kismi tahsilat: 12.000 alacak, 5.000 tahsil -> 102/120, kalan 7.000."""
    doc = _collection_doc("5000", payment_method="banka")
    entry = _collection_entry("102", "5000")
    result = reconcile_receivable_collection(doc, entry.to_dict(), "12000")
    assert result.status == ReconciliationResult.MATCH, result
    assert result.collection_type == "partial"
    assert result.payment_account == "102"
    assert result.collected_amount == Decimal("5000.00")
    assert result.remaining_receivable == Decimal("7000.00"), result.remaining_receivable


def test_phase4_b_partial_cash_collection_match():
    """B) Kasadan kismi tahsilat: 100 Dr / 120 Cr."""
    doc = _collection_doc("5000", payment_method="nakit")
    entry = _collection_entry("100", "5000")
    result = reconcile_receivable_collection(doc, entry.to_dict(), "12000")
    assert result.status == ReconciliationResult.MATCH, result
    assert result.collection_type == "partial"
    assert result.payment_account == "100"
    assert result.remaining_receivable == Decimal("7000.00")


def test_phase4_c_full_collection_closes_receivable():
    """C) Tam tahsilat: 12.000 alacak, 12.000 tahsil -> kalan 0."""
    doc = _collection_doc("12000", payment_method="banka")
    entry = _collection_entry("102", "12000")
    result = reconcile_receivable_collection(doc, entry.to_dict(), "12000")
    assert result.status == ReconciliationResult.MATCH, result
    assert result.collection_type == "full"
    assert result.remaining_receivable == Decimal("0.00")


def test_phase4_d_installments_each_collection_is_its_own_event():
    """D) Birden fazla taksit: her taksit kendi cagrisiyla, onceki kalan uzerinden
    dogrulanir. 12.000 -> 4.000 (kalan 8.000) -> 3.000 (kalan 5.000)."""
    first_doc = _collection_doc("4000", payment_method="banka")
    first_entry = _collection_entry("102", "4000")
    first = reconcile_receivable_collection(first_doc, first_entry.to_dict(), "12000")
    assert first.status == ReconciliationResult.MATCH, first
    assert first.collection_type == "partial"
    assert first.remaining_receivable == Decimal("8000.00")

    second_doc = _collection_doc("3000", payment_method="banka")
    second_entry = _collection_entry("102", "3000")
    second = reconcile_receivable_collection(second_doc, second_entry.to_dict(),
                                             first.remaining_receivable)
    assert second.status == ReconciliationResult.MATCH, second
    assert second.collection_type == "partial"
    assert second.remaining_receivable == Decimal("5000.00")


def test_phase4_e_overcollection_rejected_not_silently_accepted():
    """E) Tahsilat > acik alacak (7.000 bakiye, 8.000 tahsil): sessizce normal
    tahsilat sayilmamali -> MISMATCH, gelir/KDV olusturulmaz."""
    doc = _collection_doc("8000", payment_method="banka")
    entry = _collection_entry("102", "8000")
    result = reconcile_receivable_collection(doc, entry.to_dict(), "7000")
    assert result.status == ReconciliationResult.MISMATCH, result
    assert result.collection_type is None
    assert result.remaining_receivable is None
    assert any("aşıyor" in d or "fazla" in d for d in result.discrepancies), result.discrepancies


def test_phase4_f_missing_collection_amount_never_invented():
    """F) Tahsilat tutari eksik: tutar uydurulmaz -> INSUFFICIENT_INFORMATION;
    tutarsiz ama dengeli kayittaki rakam belge yerine 'tahsilat' sayilmaz."""
    doc = _collection_doc(None, payment_method="banka")
    entry = _collection_entry("102", "5000")
    result = reconcile_receivable_collection(doc, entry.to_dict(), "12000")
    assert result.status == ReconciliationResult.INSUFFICIENT_INFORMATION, result
    assert doc.net_amount is None  # yukari akis sessizce doldurulmadi
    assert result.collected_amount is None
    assert any("Tahsilat tutarı" in m for m in result.missing_information)


def test_phase4_g_missing_payment_channel_never_invented():
    """G) Odeme kanali eksik: 100/102 secimi uydurulmaz -> INSUFFICIENT_INFORMATION."""
    doc = _collection_doc("5000", payment_method=None)
    entry = _collection_entry("102", "5000")
    result = reconcile_receivable_collection(doc, entry.to_dict(), "12000")
    assert result.status == ReconciliationResult.INSUFFICIENT_INFORMATION, result
    assert any("ödeme şekli" in m for m in result.missing_information), result.missing_information


def test_phase4_e2_missing_outstanding_balance_never_invented():
    """E/I tamamlayici: acik bakiye verilmeden kismi/tam ayrimi yapilamaz;
    bakiye uydurulmaz -> INSUFFICIENT_INFORMATION."""
    doc = _collection_doc("5000", payment_method="banka")
    entry = _collection_entry("102", "5000")
    result = reconcile_receivable_collection(doc, entry.to_dict(), None)
    assert result.status == ReconciliationResult.INSUFFICIENT_INFORMATION, result
    assert result.collection_type is None
    assert result.remaining_receivable is None
    assert any("Açık alacak bakiyesi" in m for m in result.missing_information)


def test_phase4_h_balanced_but_wrong_collection_rejected():
    """H) Dengeli ama yanlis: tahsilat 102 Dr / 600 Cr (satis hasilati) olarak
    yazilmis. Dengeli olmasi MATCH icin yeterli degil -> MISMATCH."""
    doc = _collection_doc("5000", payment_method="banka")
    entry = (JournalEntry("yanlis tahsilat")
             .debit("102", "5000")
             .credit("600", "5000"))
    assert entry.total_debit == entry.total_credit == Decimal("5000.00")  # dengeli
    result = reconcile_receivable_collection(doc, entry.to_dict(), "12000")
    assert result.status == ReconciliationResult.MISMATCH, result
    assert any("600/391" in d or "120" in d for d in result.discrepancies), result.discrepancies


def test_phase4_i_collection_must_not_recreate_revenue_or_vat():
    """I) Kismi tahsilatta 600/391 yeniden yazilmis kayit yanlis -> MISMATCH."""
    doc = _collection_doc("5000", payment_method="banka")
    entry = _sale_entry("102", "5000", "4237.29", "762.71")  # 600/391 satirli "tahsilat"
    result = reconcile_receivable_collection(doc, entry.to_dict(), "12000")
    assert result.status == ReconciliationResult.MISMATCH, result
    assert any("600/391" in d for d in result.discrepancies), result.discrepancies


def test_phase4_j_decimal_precision_no_float_error():
    """J) Ondalikli TL degerlerinde binary float hatasi olmamali:
    12.000,50 - 5.000,25 = 7.000,25 (Decimal, bire bir)."""
    doc = _collection_doc("5000.25", payment_method="banka")
    entry = _collection_entry("102", "5000.25")
    result = reconcile_receivable_collection(doc, entry.to_dict(), "12000.50")
    assert result.status == ReconciliationResult.MATCH, result
    assert result.collected_amount == Decimal("5000.25")
    assert result.remaining_receivable == Decimal("7000.25")
    assert isinstance(result.remaining_receivable, Decimal)


def test_phase4_float_inputs_rejected_not_coerced():
    """Guvenlik: binary float para degeri (5.000,25'in float hali gibi) sessizce para
    kabul edilmez; tutar/bakiye belirlenememis sayilir."""
    doc = _collection_doc("5000.25", payment_method="banka")
    entry = _collection_entry("102", "5000.25")
    result = reconcile_receivable_collection(doc, entry.to_dict(), 12000.50)  # float
    assert result.status == ReconciliationResult.INSUFFICIENT_INFORMATION, result
    assert result.outstanding_receivable is None


# ------------------------------------------------------------------ SAFETY ----------

def test_safety_phase1_journal_path_untouched_by_phase4():
    """Phase-1 negatif kontrol: siradan yevmiye sorusu Phase-4 kodunu hic cagirmaz."""
    with engine() as e:
        e.cevap_ver('Kasadan bankaya 5.000 TL yatırdım.')
        t = e.brain.last_trace
        assert t.reconciliation_status is None
        assert t.document_validation is None
        assert t.collection_details is None
        assert t.discrepancies == []
        assert t.missing_information == []
        assert t.journal_entry is not None
        assert t.route == 'journal'


def test_safety_phase2_purchase_reconciliation_unchanged():
    """Phase-2 deseninin dogrudan fonksiyonu Phase-4'ten etkilenmemeli."""
    doc = document_from_raw(
        document_type="purchase_invoice", document_number="FTR-2026-0001",
        document_date="2026-10-01", counterparty="Örnek Satıcı A.Ş.",
        payment_method="vadeli", net="10000", vat_amount="2000", gross="12000",
    )
    entry = (JournalEntry("alis")
             .debit("153", "10000").debit("191", "2000").credit("320", "12000"))
    result = reconcile_document_entry_phase2(doc, entry.to_dict())
    assert result.status == ReconciliationResult.MATCH, result


def reconcile_document_entry_phase2(doc, entry_dict):
    """Phase-2 fonksiyonunu Phase-4 katmanindan BAGIMSIZ cagir (degismedi kontrolu)."""
    from accounting.document_reconciliation import reconcile_document_entry
    return reconcile_document_entry(doc, entry_dict, trace=None)


def test_safety_phase3_document_reconciliation_unchanged():
    """Phase-3 mevcut tahsilat-vs-satis ayrimi aynen calismaya devam etmeli."""
    doc = _collection_doc("12000", payment_method="banka")
    entry = _collection_entry("102", "12000")
    from accounting.document_reconciliation import reconcile_document_entry
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MATCH, result
    # Phase-3 fonksiyonu Phase-4 pozisyon alanlari TASIMAMALI
    assert not hasattr(result, "collection_type") or getattr(result, "collection_type", None) is None


def test_safety_phase4_result_is_phase23_result_subclass():
    """ReceivableCollectionResult mevcut ReconciliationResult status sozlesmesini aynen
    tasir (MATCH/MISMATCH/INSUFFICIENT_INFORMATION/INVALID_DOCUMENT/INVALID_ENTRY)."""
    result = reconcile_receivable_collection(
        _collection_doc("5000", "banka"), _collection_entry("102", "5000").to_dict(), "12000")
    assert isinstance(result, ReconciliationResult)
    assert isinstance(result, ReceivableCollectionResult)
    assert result.MATCH == ReconciliationResult.MATCH


# ------------------------------------------------------------------ RUNTIME ---------

def test_runtime_partial_collection_via_production_api():
    with engine() as e:
        doc = _collection_doc("5000", payment_method="banka")
        entry = _collection_entry("102", "5000")
        answer = e.reconcile_collection(doc, entry, "12000")
        assert "MATCH" in answer and "MISMATCH" not in answer
        assert "7.000" in answer or "7000" in answer
        t = e.brain.last_trace
        assert t.route == "receivable_collection"
        assert t.reconciliation_status == "MATCH"
        assert t.collection_details is not None
        assert t.collection_details["event_type"] == "receivable_collection"
        assert t.collection_details["collection_type"] == "partial"
        assert t.collection_details["payment_account"] == "102"
        assert t.collection_details["collected_amount"] == "5000.00"
        assert t.collection_details["remaining_receivable"] == "7000.00"
        assert t.collection_details["reconciliation_status"] == "MATCH"


def test_runtime_full_collection_via_production_api():
    with engine() as e:
        doc = _collection_doc("12000", payment_method="banka")
        entry = _collection_entry("102", "12000")
        answer = e.reconcile_collection(doc, entry, "12000")
        assert "tamamen kapandı" in answer
        assert e.brain.last_trace.collection_details["collection_type"] == "full"
        assert e.brain.last_trace.collection_details["remaining_receivable"] == "0.00"


def test_runtime_overcollection_rejected_via_production_api():
    with engine() as e:
        doc = _collection_doc("8000", payment_method="banka")
        entry = _collection_entry("102", "8000")
        answer = e.reconcile_collection(doc, entry, "7000")
        assert "MISMATCH" in answer
        t = e.brain.last_trace
        assert t.reconciliation_status == "MISMATCH"
        assert t.collection_details["reconciliation_status"] == "MISMATCH"
        assert t.collection_details["collection_type"] is None


def test_runtime_trace_fields_real_and_serializable():
    """Trace gercekten olusur ve to_dict() Phase-4 alanlarini icerir."""
    with engine() as e:
        doc = _collection_doc("5000", payment_method="nakit")
        entry = _collection_entry("100", "5000")
        e.reconcile_collection(doc, entry, "12000")
        t = e.brain.last_trace
        d = t.to_dict()
        assert d["route"] == "receivable_collection"
        assert d["confidence"] == "VERIFIED"
        assert d["deterministic_tool"] == "receivable_collection"
        assert d["deterministic_tool_used"] is True
        assert d["collection_details"]["payment_account"] == "100"
        assert t.model_calls == 0 and t.used_model is False  # model cagrisi yok


def test_runtime_phase3_reconcile_document_still_works_alongside_phase4():
    """Phase-4 eklendikten sonra Phase-3 uretim girisi (reconcile_document) degismedi."""
    with engine() as e:
        doc = _collection_doc("12000", payment_method="banka")
        entry = _collection_entry("102", "12000")
        answer = e.reconcile_document(doc, entry)
        assert "MATCH" in answer
        t = e.brain.last_trace
        assert t.route == "document_reconciliation"
        assert t.reconciliation_status == "MATCH"
        assert t.collection_details is None  # Phase-4 trace alani Phase-3 cagrisinda KALAN None
