"""Accountant Phase 2: document <-> journal reconciliation.

FOCUSED tests (A-J) exercise `reconcile_document_entry` directly against the real
Phase-1 `accounting.journal` entries/dicts -- no engine, no model, no network.
RUNTIME tests (A-E incl. G) exercise the real production path:
`KaizenEngine.reconcile_document` (new) and `KaizenEngine.cevap_ver` (unchanged,
Phase-1 negative control) through the same isolated-store harness as
tests/test_accountant_phase1.py.
"""
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from config.config_manager import ConfigManager
from core.engine import KaizenEngine
from core.ai.offline_provider import OfflineProvider
from tests.doubles import NullExperienceMemory

from accounting.journal import purchase_goods, JournalEntry
from accounting.document_reconciliation import (
    NormalizedDocument,
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


def _doc(net=None, vat_rate=None, vat_amount=None, gross=None, payment_method=None,
         line_items=None, document_type="purchase_invoice"):
    return document_from_raw(
        document_type=document_type,
        document_number="FTR-2026-0001",
        document_date="2026-10-01",
        counterparty="Örnek Tedarikçi A.Ş.",
        payment_method=payment_method,
        net=net, vat_rate=vat_rate, vat_amount=vat_amount, gross=gross,
        line_items=line_items,
    )


def _manual_entry(lines, debit_total, credit_total, description="manual"):
    """A hand-built already-booked entry dict (as if it came from elsewhere), in the
    exact Phase-1 JournalEntry.to_dict() shape -- deliberately bypasses
    JournalEntry.validate() so an unbalanced/legacy entry can be represented."""
    return {
        "description": description, "status": "PROPOSED", "entry_date": None,
        "lines": [{"account_code": a, "account_name": n, "debit": str(d), "credit": str(cr),
                   "rationale": "manual", "source_reference": "manual"} for a, n, d, cr in lines],
        "debit_total": str(debit_total), "credit_total": str(credit_total), "notes": [],
    }


# ------------------------------------------------------------------ FOCUSED A-J ------

def test_focused_a_exact_match_credit_purchase():
    doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="vadeli")
    entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="vadeli")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MATCH, result
    assert not result.discrepancies


def test_focused_b_balanced_but_wrong_is_mismatch_not_match():
    doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="banka")
    # Balanced (900+200=1100=credit) but wrong net/VAT split vs the document.
    wrong = JournalEntry("yanlis").debit("153", "900").debit("191", "200").credit("102", "1100")
    assert wrong.total_debit == wrong.total_credit == Decimal("1100.00")  # genuinely balanced
    result = reconcile_document_entry(doc, wrong.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result
    assert any("Net tutar" in d or "KDV uyuşmazlığı" in d for d in result.discrepancies), result.discrepancies


def test_focused_c_payment_method_mismatch_bank_vs_kasa():
    doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="banka")
    entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="nakit")  # settled via 100 Kasa
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result
    assert any("Kasa" in d for d in result.discrepancies), result.discrepancies


def test_focused_d_missing_vat_is_insufficient_information():
    doc = _doc(net="1000", vat_rate=None, vat_amount=None, gross=None, payment_method="banka")
    entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="banka")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.INSUFFICIENT_INFORMATION, result
    assert "KDV oranı veya KDV tutarı nedir?" in result.missing_information
    assert not any("%20" in m or "20" in m for m in result.missing_information)  # no invented rate


def test_focused_e_invalid_document_arithmetic():
    doc = _doc(net="1000", vat_amount="100", gross="2000", payment_method="banka")  # 1000+100 != 2000
    entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="banka")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.INVALID_DOCUMENT, result
    assert doc.gross_amount == Decimal("2000")  # never silently corrected to 1100


def test_focused_f_unbalanced_entry_is_invalid_entry():
    doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="banka")
    bad = _manual_entry(
        [("153", "Ticari Mallar", "1000", "0"), ("191", "İndirilecek KDV", "100", "0"),
         ("102", "Bankalar", "0", "1099")],
        debit_total="1100", credit_total="1099",
    )
    result = reconcile_document_entry(doc, bad, trace=None)
    assert result.status == ReconciliationResult.INVALID_ENTRY, result


def test_focused_g_reconciliation_fields_untouched_by_normal_answer():
    """Phase-1 negative control at the trace level: an ordinary accounting question
    must leave every Phase-2 trace field at its untouched default."""
    with engine() as e:
        e.cevap_ver('Kasadan bankaya 5.000 TL yatırdım.')
        t = e.brain.last_trace
        assert t.reconciliation_status is None
        assert t.document_validation is None
        assert t.discrepancies == []
        assert t.missing_information == []
        assert t.journal_entry is not None  # Phase-1 own journal_entry field still works


def test_focused_h_correct_bank_payment_is_match():
    doc = _doc(net="5000", vat_amount="900", gross="5900", payment_method="banka")
    entry = purchase_goods(Decimal("5000"), Decimal("18"), mode="banka")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MATCH, result


def test_focused_i_credit_purchase_semantics_violated():
    doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="vadeli")
    entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="banka")  # settled 102, not 320
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.MISMATCH, result
    assert any("vadeli" in d.lower() or "kredili" in d.lower() for d in result.discrepancies), result.discrepancies


def test_focused_j_line_item_error_is_invalid_document():
    doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="banka",
                line_items=["400", "400"])  # sums to 800, not 1000
    entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="banka")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=None)
    assert result.status == ReconciliationResult.INVALID_DOCUMENT, result
    assert result.discrepancies  # explicit discrepancy present either way


# ------------------------------------------------------------------ SAFETY -----------

def test_safety_decimal_money_only():
    try:
        NormalizedDocument(net_amount=1000.0)  # binary float, not Decimal/str
    except Exception:
        pass
    assert NormalizedDocument._to_decimal(1000.0) is None  # float never silently accepted
    assert NormalizedDocument._to_decimal("1000") == Decimal("1000")


def test_safety_trace_recording_direct_attribute_assignment():
    """KaizenTrace has no record_reconciliation() method -- reconciliation sets its
    fields directly, same convention as every other route in core/kaizen_brain.py."""
    from core.trace import KaizenTrace
    trace = KaizenTrace()
    doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="vadeli")
    entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="vadeli")
    result = reconcile_document_entry(doc, entry.to_dict(), trace=trace)
    assert trace.reconciliation_status == result.status == ReconciliationResult.MATCH
    assert trace.document_validation is not None
    assert trace.discrepancies == []
    assert not hasattr(trace, "record_reconciliation")


# ------------------------------------------------------------------ RUNTIME A-E ------

def test_runtime_a_exact_match():
    with engine() as e:
        doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="vadeli")
        entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="vadeli")
        answer = e.reconcile_document(doc, entry)
        assert "MATCH" in answer and "MISMATCH" not in answer
        assert e.brain.last_trace.reconciliation_status == "MATCH"


def test_runtime_b_balanced_but_wrong_is_mismatch():
    with engine() as e:
        doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="banka")
        wrong = JournalEntry("yanlis").debit("153", "900").debit("191", "200").credit("102", "1100")
        answer = e.reconcile_document(doc, wrong)
        assert "MISMATCH" in answer
        assert e.brain.last_trace.reconciliation_status == "MISMATCH"


def test_runtime_c_payment_method_mismatch():
    with engine() as e:
        doc = _doc(net="1000", vat_amount="100", gross="1100", payment_method="banka")
        entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="nakit")
        answer = e.reconcile_document(doc, entry)
        assert "MISMATCH" in answer
        assert e.brain.last_trace.reconciliation_status == "MISMATCH"


def test_runtime_d_missing_vat_asks_targeted_clarification():
    with engine() as e:
        doc = _doc(net="1000", vat_rate=None, vat_amount=None, gross=None, payment_method="banka")
        entry = purchase_goods(Decimal("1000"), Decimal("10"), mode="banka")
        answer = e.reconcile_document(doc, entry)
        assert "INSUFFICIENT_INFORMATION" in answer
        assert "KDV oranı veya KDV tutarı nedir?" in answer
        assert e.brain.last_trace.reconciliation_status == "INSUFFICIENT_INFORMATION"


def test_runtime_e_invalid_document_not_silently_corrected():
    with engine() as e:
        doc = _doc(net="1800", vat_amount="0", gross="2000", payment_method="banka")  # 1800+0 != 2000
        entry = purchase_goods(Decimal("1800"), Decimal("0"), mode="banka")
        answer = e.reconcile_document(doc, entry)
        assert "INVALID_DOCUMENT" in answer
        assert "MATCH" not in answer.replace("MISMATCH", "").replace("INVALID_DOCUMENT", "")
        # The document's own stated value is never silently changed to the "correct" 2000.
        assert doc.net_amount == Decimal("1800") and doc.gross_amount == Decimal("2000")
        assert e.brain.last_trace.reconciliation_status == "INVALID_DOCUMENT"


def test_runtime_g_phase1_negative_control_unaffected():
    """Scenario G: an ordinary Phase-1 accounting question must NOT enter
    reconciliation at all -- same production path, same answer as before Phase 2."""
    with engine() as e:
        answer = e.cevap_ver('Kasadan bankaya 5.000 TL yatırdım.')
        t = e.brain.last_trace
        j = t.journal_entry
        assert j is not None
        lines = {x['account_code']: (Decimal(x['debit']), Decimal(x['credit'])) for x in j['lines']}
        assert lines == {'102': (Decimal('5000'), Decimal('0')), '100': (Decimal('0'), Decimal('5000'))}
        assert t.reconciliation_status is None and t.document_validation is None
        assert t.route == 'journal'
