"""Accounting behavior through the real production router; isolated stores, no external calls."""
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from config.config_manager import ConfigManager
from core.engine import KaizenEngine
from core.ai.offline_provider import OfflineProvider
from tests.doubles import NullExperienceMemory
from accounting.journal import JournalEntry, JournalLine, JournalError

@contextmanager
def engine():
    with TemporaryDirectory() as tmp:
        c=ConfigManager();c.config['retrieval']['hybrid_enabled']=False;c.config['research']['research_engine_enabled']=False
        e=KaizenEngine(data_dir=Path(tmp)/'data',log_dir=Path(tmp)/'logs',config=c,provider=OfflineProvider(),experience_memory=NullExperienceMemory())
        try:yield e
        finally:e.shutdown()

def entry_case(q,expected,total):
    with engine() as e:
        answer=e.cevap_ver(q);t=e.brain.last_trace;j=t.journal_entry
        assert j is not None,(q,answer,t.to_dict())
        lines={x['account_code']:(Decimal(x['debit']),Decimal(x['credit'])) for x in j['lines']}
        assert lines=={k:(Decimal(a),Decimal(b)) for k,(a,b) in expected.items()},(q,lines)
        assert Decimal(j['debit_total'])==Decimal(j['credit_total'])==Decimal(total)
        assert t.model_calls==0 and not t.used_research
        assert set(t.principle_ids)=={'borc_alacak','hesap_siniflandirma'}
        assert all(l['rationale'] and l['source_reference'] for l in j['lines'])
        assert {effect['account'] for effect in t.accounting_reasoning_context['account_effects']} == set(lines)
        return answer

def clarification(q,field):
    with engine() as e:
        answer=e.cevap_ver(q);t=e.brain.last_trace
        assert field in t.missing_facts,(q,answer,t.to_dict())
        assert t.journal_entry is None and t.confidence!='VERIFIED'
        assert t.model_calls==0 and not t.used_research
        assert t.accounting_reasoning_context['missing_information']==t.missing_facts
        return answer

def test_01_deferred_purchase():
    entry_case('Vadeli KDV hariç 10.000 TL ticari mal aldım, KDV oranı %10.',{'153':('10000','0'),'191':('1000','0'),'320':('0','11000')},'11000')
    clarification('Vadeli 10.000 TL ticari mal aldım, KDV oranı %10.','amount_basis')
def test_02_cash_purchase():
    entry_case('Nakit 1.000 TL + %10 KDV ticari mal aldım.',{'153':('1000','0'),'191':('100','0'),'100':('0','1100')},'1100')
def test_03_bank_purchase():
    entry_case('1.000 TL + %10 KDV ticari mal aldım, bankadan ödedim.',{'153':('1000','0'),'191':('100','0'),'102':('0','1100')},'1100')
def test_04_missing_vat():
    a=clarification('12.000 TL + KDV demirbaş aldım.','vat_rate');assert '%20' not in a
    clarification('KDV dahil 11.000 TL mal aldım.','vat_rate')
def test_05_cash_to_bank():
    entry_case('Kasadan bankaya 5.000 TL yatırdım.',{'102':('5000','0'),'100':('0','5000')},'5000')
def test_06_customer_collection():
    entry_case('Müşteriden 3.000 TL alacağımı nakit tahsil ettim.',{'100':('3000','0'),'120':('0','3000')},'3000')
def test_07_vendor_payment():
    entry_case('Satıcıya olan 8.000 TL borcumu banka hesabından ödedim.',{'320':('8000','0'),'102':('0','8000')},'8000')
def test_08_expense():
    entry_case('7/A genel yönetim elektrik gider faturası 1.000 TL + %10 KDV, bankadan ödendi.',{'770':('1000','0'),'191':('100','0'),'102':('0','1100')},'1100')
def test_09_asset():
    entry_case('İşletmede kullanmak için demirbaş aldım, 12.000 TL + %10 KDV, vadeli.',{'255':('12000','0'),'191':('1200','0'),'320':('0','13200')},'13200')
def test_10_ambiguous():
    clarification('Peşin 1.000 TL + %10 KDV ticari mal aldım.','payment_method')
    clarification('1.000 TL bir şey aldım.','transaction_nature')
    clarification('8.000 TL borcumu ödedim.','counterparty_role')
def test_11_bad_journal_rejected():
    with engine() as e,patch('accounting.journal.cash_deposit',return_value=JournalEntry('bad').debit('102','100').credit('100','99')):
        a=e.cevap_ver('Kasadan bankaya 100 TL yatırdım.')
        assert e.brain.last_trace.invariant_failures and e.brain.last_trace.journal_entry is None
        assert e.brain.last_trace.confidence!='VERIFIED' and 'oluşturulamadı' in a
    bad=JournalEntry('bad').debit('102','100').credit('100','99')
    try:bad.render()
    except JournalError:pass
    else:raise AssertionError('unbalanced journal rendered')
def test_12_current_fact_boundary():
    with engine() as e:
        a=e.cevap_ver('2098 yılı fatura düzenleme sınırı nedir?')
        assert e.brain.last_trace.used_facts and e.brain.last_trace.journal_entry is None
        assert e.brain.last_trace.route=='not_found_offline'
        assert e.brain.last_trace.model_calls==0
        assert 'doğrula' in a.lower() or 'bulamad' in a.lower()
def test_13_colloquial():
    entry_case('Veresiye 2.000 TL + %10 KDV mal aldım.',{'153':('2000','0'),'191':('200','0'),'320':('0','2200')},'2200')
def test_14_distractor():
    entry_case('Mal almadım. Kasadan bankaya 5.000 TL yatırdım.',{'102':('5000','0'),'100':('0','5000')},'5000')
def test_exact_money_and_rounding():
    entry_case('Vadeli KDV dahil 0,07 TL mal aldım, KDV oranı %20.',{'153':('0.06','0'),'191':('0.01','0'),'320':('0','0.07')},'0.07')
    try:JournalLine('100',debit=0.1)
    except JournalError:pass
    else:raise AssertionError('binary float accepted')
    with engine() as e:
        e.cevap_ver('Kasadan bankaya -5.000 TL yatırdım.')
        assert e.brain.last_trace.invariant_failures and e.brain.last_trace.journal_entry is None
def test_special_tax_and_expense_ambiguity():
    clarification('Vadeli binek otomobil aldım 100.000 TL + %10 KDV.','verified_tax_treatment')
    clarification('1.000 TL + %10 KDV elektrik faturası, bankadan ödendi.','expense_function')
    clarification('Vadeli toplam 1.000 TL mal aldım KDV %10.','amount_basis')
    clarification('Vadeli nakit 1.000 TL + %10 KDV mal aldım.','conflicting_payment')
def test_normalized_existing_principles():
    with engine() as e:
        e.cevap_ver('Kasadan bankaya 5.000 TL yatırdım.')
        for p in e.brain.last_trace.accounting_pipeline['principles']:
            assert set(('principle_id','name','scope','conditions','accounting_effect','exceptions','required_facts','source_requirement','confidence','validation_state')).issubset(p)
            assert e.principle_registry.get(p['principle_id']) is not None

def test_event_negation_and_account_side():
    clarification('Kasadan bankaya 5.000 TL yatırmadım.','event_occurred')
    clarification('Müşteriden 3.000 TL nakit tahsil etmedim.','event_occurred')
    clarification('Bankadan kasaya 5.000 TL yatırdım.','transfer_direction')
    entry_case('1.000 TL + %10 KDV mal aldım, henüz ödemedim.',{'153':('1000','0'),'191':('100','0'),'320':('0','1100')},'1100')
    with engine() as e,patch('accounting.journal.cash_deposit',return_value=JournalEntry('reversed').debit('100','100').credit('102','100')):
        e.cevap_ver('Kasadan bankaya 100 TL yatırdım.')
        assert e.brain.last_trace.invariant_failures and e.brain.last_trace.journal_entry is None
