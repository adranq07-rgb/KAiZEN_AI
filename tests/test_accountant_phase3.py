"""Accountant Phase 3: sales-side (receivable) document <-> journal reconciliation.

Extends Phase 2's reconcile_document_entry with: credit/cash/bank sale semantics,
and the collection-of-an-existing-receivable vs new-sale distinction. No new engine,
no new production entry point -- same KaizenBrain.reconcile_document /
KaizenEngine.reconcile_document path as Phase 2.

FOCUSED tests (A-L) call reconcile_document_entry directly against real Phase-1
JournalEntry objects/dicts. Two RUNTIME tests exercise the real production path
(KaizenEngine.reconcile_document) plus the Phase-1 negative control.
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
from accounting.document_reconciliation import (
    ReconciliationResult,
    document_from_raw,
    reconcile_document_entry,
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


def _sale_doc(net=None, vat_amount=None, gross=None, payment_method=None,
              document_type="sales_invoice"):
    return document_from_raw(
        document_type=document_type, document_number="FTR-S-2026-0001",
        document_date="2026-10-01", counterparty="Örnek Müşteri A.Ş.",
        payment_method=payment_method, net=net, vat_amount=vat_amount, gross=gross,
    )


def _collection_doc(amount, payment_method):
    return document_from_raw(
        document_type="tahsilat", document_number="TAH-2026-0001",
        document_date="2026-10-01", counterparty="Örnek Müşteri A.Ş.",
        payment_method=payment_method, net=amount,
    )


def _sale_entry(receivable_or_cash_account, amount, net, vat, description="satis"):
    return (JournalEntry(description)
            .debit(receivable_or_cash_account, amount)
            .credit("600", net)
            .credit("391", vat))


def _collection_entry(cash_or_bank_account, amount, description="tahsilat"):
    return (JournalEntry(description)
            .debit(cash_or_bank_account, amount)
            .credit("120", amount))


def _manual_entry(lines, debit_total, credit_total, description="manual"):
    return {
        "description": description, "status": "PROPOSED", "entry_date": None,
        "lines": [{"account_code": a, "account_name": n, "debit": str(d), "credit": str(cr),
                   "rationale": "manual", "source_reference": "manual"} for a, n, d, cr in lines],
        "debit_total": str(debit_total), "credit_total": str(credit_total), "notes": [],
    }


# ------------------------------------------------------------------ FOCUSED A-L ------

def test_focused_a_credit_sale_exact_match():
    doc = _sale_doc(net="10000", vat_amount="2000", gross="12000", payment_method="vadeli")
    entry = _sale_entry("120", "12000", "10000", "2000")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MATCH, result


def test_focused_b_balanced_but_wrong_vat():
    doc = _sale_doc(net="10000", vat_amount="2000", gross="12000", payment_method="vadeli")
    entry = _sale_entry("120", "11800", "10000", "1800")  # balanced (11800 == 10000+1800)
    assert entry.total_debit == entry.total_credit == Decimal("11800.00")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result


def test_focused_c_credit_sale_wrongly_recorded_as_bank_receipt():
    doc = _sale_doc(net="10000", vat_amount="2000", gross="12000", payment_method="vadeli")
    entry = _sale_entry("102", "12000", "10000", "2000")  # should have been 120
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result
    assert any("120" in d for d in result.discrepancies), result.discrepancies


def test_focused_d_bank_sale_exact_match():
    doc = _sale_doc(net="10000", vat_amount="2000", gross="12000", payment_method="banka")
    entry = _sale_entry("102", "12000", "10000", "2000")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MATCH, result


def test_focused_e_cash_bank_contradiction():
    doc = _sale_doc(net="10000", vat_amount="2000", gross="12000", payment_method="nakit")
    entry = _sale_entry("102", "12000", "10000", "2000")  # document says cash, entry used bank
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result


def test_focused_f_vat_missing_is_insufficient_information():
    doc = _sale_doc(net="10000", vat_amount=None, gross=None, payment_method="banka")
    entry = _sale_entry("102", "12000", "10000", "2000")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.INSUFFICIENT_INFORMATION, result
    assert "KDV oranı veya KDV tutarı nedir?" in result.missing_information
    assert not any("%20" in m for m in result.missing_information)


def test_focused_g_invalid_sales_document():
    doc = _sale_doc(net="10000", vat_amount="2000", gross="11500", payment_method="vadeli")  # != 12000
    entry = _sale_entry("120", "12000", "10000", "2000")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.INVALID_DOCUMENT, result
    assert doc.gross_amount == Decimal("11500")  # never silently corrected


def test_focused_h_invalid_journal_unbalanced():
    doc = _sale_doc(net="10000", vat_amount="2000", gross="12000", payment_method="vadeli")
    bad = _manual_entry(
        [("120", "Alıcılar", "11999", "0"), ("600", "Yurt İçi Satışlar", "0", "10000"),
         ("391", "Hesaplanan KDV", "0", "2000")],
        debit_total="11999", credit_total="12000",
    )
    result = reconcile_document_entry(doc, bad, trace=None)
    assert result.status == ReconciliationResult.INVALID_ENTRY, result


def test_focused_i_bank_collection_of_existing_receivable_is_match():
    doc = _collection_doc("12000", payment_method="banka")
    entry = _collection_entry("102", "12000")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MATCH, result
    assert not result.discrepancies


def test_focused_j_collection_incorrectly_recorded_as_new_sale():
    doc = _collection_doc("12000", payment_method="banka")
    entry = _sale_entry("102", "12000", "10000", "2000")  # has 600/391 -- not a plain collection
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result
    assert any("600/391" in d or "tahsilat" in d.lower() for d in result.discrepancies), result.discrepancies


def test_focused_k_credit_sale_missing_120():
    doc = _sale_doc(net="10000", vat_amount="2000", gross="12000", payment_method="vadeli")
    entry = _sale_entry("100", "12000", "10000", "2000")  # Kasa instead of Alıcılar
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result


def test_focused_l_normal_answer_untouched_by_reconciliation_fields():
    """Phase-1 negative control at trace level (mirrors Phase 2's focused_g)."""
    with engine() as e:
        e.cevap_ver('Kasadan bankaya 5.000 TL yatırdım.')
        t = e.brain.last_trace
        assert t.reconciliation_status is None
        assert t.document_validation is None
        assert t.discrepancies == []
        assert t.missing_information == []
        assert t.journal_entry is not None


# ------------------------------------------------------------------ SAFETY -----------

def test_safety_cash_bank_sale_but_120_present_is_mismatch():
    """Immediate (cash/bank) sale document, but journal still shows an uncollected
    receivable (120) instead of 100/102 -- the mirror image of credit-but-100/102."""
    doc = _sale_doc(net="10000", vat_amount="2000", gross="12000", payment_method="banka")
    entry = _sale_entry("120", "12000", "10000", "2000")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result
    assert any("120" in d for d in result.discrepancies), result.discrepancies


def test_safety_collection_amount_mismatch_is_detected():
    doc = _collection_doc("12000", payment_method="banka")
    entry = _collection_entry("102", "11000")  # wrong collected amount, still balanced
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result


# ------------------------------------------------------------------ RUNTIME (compat) -

def test_runtime_credit_sale_match_via_production_api():
    with engine() as e:
        doc = _sale_doc(net="10000", vat_amount="2000", gross="12000", payment_method="vadeli")
        entry = _sale_entry("120", "12000", "10000", "2000")
        answer = e.reconcile_document(doc, entry)
        assert "MATCH" in answer and "MISMATCH" not in answer
        assert e.brain.last_trace.reconciliation_status == "MATCH"


def test_runtime_collection_match_via_production_api():
    with engine() as e:
        doc = _collection_doc("12000", payment_method="banka")
        entry = _collection_entry("102", "12000")
        answer = e.reconcile_document(doc, entry)
        assert "MATCH" in answer
        assert e.brain.last_trace.reconciliation_status == "MATCH"


def test_runtime_phase1_negative_control_unaffected():
    with engine() as e:
        answer = e.cevap_ver('Kasadan bankaya 5.000 TL yatırdım.')
        t = e.brain.last_trace
        j = t.journal_entry
        lines = {x['account_code']: (Decimal(x['debit']), Decimal(x['credit'])) for x in j['lines']}
        assert lines == {'102': (Decimal('5000'), Decimal('0')), '100': (Decimal('0'), Decimal('5000'))}
        assert t.reconciliation_status is None and t.route == 'journal'
