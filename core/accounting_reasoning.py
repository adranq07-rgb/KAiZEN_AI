"""Source-backed accounting context consumed by the existing grounded answer path.

Linguistic signals nominate an event; curated template text and the chart validate
its account effects. No account codes, directions or rates are inferred from a
language model. ReflectionLifecycle persists the existing structural metadata.
"""

import re
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional

from learning.question_profile import profile_question
from learning.strategy_catalog import (
    ASK_MISSING, PERIOD_SEPARATION, PRINCIPLE_GROUNDED, RESEARCH_FIRST,
    STRATEGIES, strategy_applies_to,
)
from core.text_tr import fold_tr


# Problem tipi sabitleri
PROBLEM_TYPE_DEFINITION = "definition"
PROBLEM_TYPE_TRANSACTION = "transaction"
PROBLEM_TYPE_JOURNAL = "journal_entry"
PROBLEM_TYPE_CALCULATION = "calculation"
PROBLEM_TYPE_CURRENT_FACT = "current_fact"
PROBLEM_TYPE_PROFESSIONAL_OPINION = "professional_opinion"
PROBLEM_TYPE_UNKNOWN = "unknown"


@dataclass
class AccountingReasoningContext:
    """Internal structured decision state for accounting questions.
    KULLANICIYA GÖSTERİLMEZ. Yalnız internal trace ve future learning için."""

    problem_type: str = ""
    accounting_domain: str = ""
    relevant_concepts: tuple = ()
    relevant_principle_ids: tuple = ()
    affected_accounts: tuple = ()
    event_type: str = ""
    payment_state: str = ""
    account_effects: tuple = ()
    principle_retrieval_status: str = "NONE_APPLICABLE"
    source_records: tuple = field(default=(), repr=False)
    deterministic_tool_needed: bool = False
    current_fact_needed: bool = False
    missing_information: tuple = ()
    evidence_needed: bool = False
    recommended_strategy: str = ""
    knowledge_sources: tuple = ()

    def to_dict(self):
        return {
            "problem_type": self.problem_type,
            "accounting_domain": self.accounting_domain,
            "relevant_concepts": list(self.relevant_concepts),
            "relevant_principle_ids": list(self.relevant_principle_ids),
            "affected_accounts": list(self.affected_accounts),
            "event_type": self.event_type,
            "payment_state": self.payment_state,
            "account_effects": list(self.account_effects),
            "principle_retrieval_status": self.principle_retrieval_status,
            "deterministic_tool_needed": self.deterministic_tool_needed,
            "current_fact_needed": self.current_fact_needed,
            "missing_information": list(self.missing_information),
            "evidence_needed": self.evidence_needed,
            "recommended_strategy": self.recommended_strategy,
            "knowledge_sources": list(self.knowledge_sources),
        }


class AccountantReasoningEngine:
    """AccountingReasoningContext oluşturan motor.

    Mevcut sınıfları reuse eder:
    - LearningStore: kavramları getirmek için
    - PrincipleRetriever: ilkeleri getirmek için
    - AccountingBrain: muhasebe alanı sınıflandırması için
    - question_profile: soru profili için
    """

    def __init__(self, learning_store=None, principle_retriever=None,
                 accounting_brain=None):
        self.learning_store = learning_store
        self.principle_retriever = principle_retriever
        self.accounting_brain = accounting_brain

    @staticmethod
    def apply_journal_result(context, result):
        """Make the exact decision authoritative for Trace and structural reflection."""
        context = context or AccountingReasoningContext()
        lines = (result.get('journal') or {}).get('lines', [])
        context.problem_type = PROBLEM_TYPE_JOURNAL
        context.event_type = result.get('event', 'journal_entry')
        context.payment_state = result.get('known_facts', {}).get('payment', 'unspecified')
        context.missing_information = tuple(result.get('missing_information', []))
        context.relevant_principle_ids = tuple(p['principle_id'] for p in result.get('principles', []))
        context.deterministic_tool_needed = True
        context.current_fact_needed = bool(result.get('knowledge_types', {}).get('current'))
        context.account_effects = tuple({
            'account': line['account_code'], 'name': line['account_name'],
            'direction': 'debit' if Decimal(line['debit']) else 'credit',
            'source': {'path': line['source_reference']}, 'chart_source': 'config/tdhp.json'
        } for line in lines)
        context.affected_accounts = tuple(line['account_code'] + ' ' + line['account_name'] for line in lines)
        context.knowledge_sources = ('validated_local_principles', 'TDHP', 'user_transaction_facts')
        return context

    def build_context(self, question, domain, current=False, previous=None):
        """Accounting sorusu için structured reasoning context oluşturur.

        Args:
            question: kullanıcı sorusu
            domain: classify() sonucu ("accounting" olmalı)
            current: needs_current_research() sonucu

        Returns:
            AccountingReasoningContext
        """
        context = AccountingReasoningContext()
        context.current_fact_needed = current

        # 1. SORUNU ANLA: problem tipi
        context.problem_type = self._classify_problem_type(question, current)

        # 2. Muhasebe alanı
        context.accounting_domain = self._get_accounting_domain(question)

        # 3. MESLEKİ BİLGİYİ GETİR: LearningStore'dan ilgili kavramlar
        context.relevant_concepts = self._retrieve_concepts(question)

        # 4. İLGİLİ PRENSİPLERİ GETİR: PrincipleRetriever'dan
        context.relevant_principle_ids, context.principle_retrieval_status = self._retrieve_principles(question)

        # 5. ETKİLENEN HESAPLAR (knowledge/templates'ten türetilmiş)
        # Account truth is accepted only after template + chart validation.
        self._resolve_purchase(question, context, previous)

        # 6. DETERMİNİSTİK İŞ VARSA ARAÇ KULLAN
        context.deterministic_tool_needed = self._needs_deterministic_tool(question)

        # 7. EKSİK BİLGİ
        context.missing_information += self._identify_missing_info(question)

        # 8. KANİT GEREKSİNİMİ
        context.evidence_needed = bool(context.relevant_concepts)

        # 9. ÖNERİLEN STRATEJİ
        context.recommended_strategy = self._recommend_strategy(context)

        # 10. BİLGİ KAYNAKLARI
        context.knowledge_sources = self._determine_sources(context)

        return context

    # ------------------------------------------------------------------
    # 1. SORUNU ANLA
    # ------------------------------------------------------------------

    def _classify_problem_type(self, question, current):
        """Sorunun problem tipini belirler.
        fold_tr sonrası kontrol yapar — 'aldım' → 'aldim' normalizasyonu."""
        folded = fold_tr(question)

        # Güncel fact mı?
        if current:
            return PROBLEM_TYPE_CURRENT_FACT

        # Matematik mi?
        if _is_calculation(question):
            return PROBLEM_TYPE_CALCULATION

        # Kayıt/yevmiye mi?
        if _is_journal_question(folded):
            return PROBLEM_TYPE_JOURNAL

        # İşlem/transaksiyon mı?
        if _is_transaction_question(folded):
            return PROBLEM_TYPE_TRANSACTION

        # Tanım/kavram mı?
        if _is_definition_question(folded):
            return PROBLEM_TYPE_DEFINITION

        # Mesleki yorum mu?
        if _is_professional_opinion(folded):
            return PROBLEM_TYPE_PROFESSIONAL_OPINION

        return PROBLEM_TYPE_UNKNOWN

    # ------------------------------------------------------------------
    # 2. MUHASEBE ALANI
    # ------------------------------------------------------------------

    def _get_accounting_domain(self, question):
        """Sorunun hangi muhasebe disiplinine ait olduğunu belirler.
        AccountingBrain.classify_topic() reuse."""
        if self.accounting_brain is not None:
            return self.accounting_brain.classify_topic(question)
        return "financial_accounting"

    # ------------------------------------------------------------------
    # 3. MESLEKİ BİLGİYİ GETİR
    # ------------------------------------------------------------------

    def _retrieve_concepts(self, question):
        """LearningStore'dan ilgili muhasebe kavramlarını getirir.
        Dönüş: (subject, section) tuple'ları — sadece document title DEĞİL,
        spesifik bölüm/kavram bilgisi."""
        if self.learning_store is None:
            return ()
        try:
            rows = self.learning_store.search(question, domain="accounting", limit=3)
            # subject + section birlikte döner — spesifik kavram/section bilgisi
            concepts = []
            for row in rows:
                subject = row.get("subject", "")
                section = row.get("section", "")
                if subject and section:
                    concepts.append(f"{subject} — {section}")
                elif subject:
                    concepts.append(subject)
            return tuple(concepts)
        except Exception:
            return ()

    # ------------------------------------------------------------------
    # 4. İLGİLİ PRENSİPLERİ GETİR
    # ------------------------------------------------------------------

    def _retrieve_principles(self, question, problem_type=None):
        if self.principle_retriever is None:
            return (), "RETRIEVAL_FAILED"
        try:
            result = self.principle_retriever.retrieve(question)
            # Rejected/lexical-only candidates are not applied principles.
            if result.selected and not result.fact_safety_triggered:
                return (result.selected,), "APPLIED"
            return (), "NONE_APPLICABLE"
        except Exception:
            return (), "RETRIEVAL_FAILED"

    @staticmethod
    def purchase_candidate(question, previous=None):
        """Small linguistic nomination only; a matching source is still mandatory."""
        text = fold_tr(question)
        if re.search(r"\b(iade\w*|sat(?:ti|is)\w*|satma\w*|satil\w*|satac\w*|satmay\w*|almad\w*|alinmad\w*|almay\w*|siparis\w*)\b", text):
            return False
        goods = bool(re.search(r"\b(mal[ıi]?|mallar\w*|stok\w*|emtia|goods|inventory)\b", text))
        acquisition = bool(re.search(r"\b(ald[ıi]\w*|alin\w*|alis\w*|alim\w*|satin\s+al\w*|purchased|bought)\b", text))
        followup = bool(previous and previous.event_type and re.search(r"\b(ayni|same)\b", text))
        return goods and (acquisition or followup)

    def _resolve_purchase(self, question, context, previous):
        if self.learning_store is None or not self.purchase_candidate(question, previous):
            return
        from accounting.chart_of_accounts import ChartOfAccounts
        text = fold_tr(question)
        rows = self.learning_store.search("ticari mal alış", domain="accounting", limit=12)
        rows = [r for r in rows if r.get("source_type") == "curated"
                and r.get("source_path") == "knowledge/muhasebe_kayit_sablonlari.json"
                and fold_tr(r.get("section", "")).startswith("ticari mal alis")]
        if len(rows) != 1:
            context.missing_information = ("mal alışına ait tekil kaynak şablonu",)
            return
        row = rows[0]
        # Parse only the normative part; illustrative rates never become facts.
        normative = re.split(r"Örnek:|Anahtar sözcükler:", row["text"])[0].strip()
        base, separator, cash_clause = normative.partition("Peşin ödemede")
        matches = re.findall(r"(\d{3})\s+([^,;.]+?) hesabına (borç|alacak)", base)
        replacement = re.search(r"(\d{3}) yerine (.+?) hesabı (borç|alacak)landırılır", cash_clause)
        chart = ChartOfAccounts()
        source = {"type": "knowledge_template", "path": row["source_path"],
                  "record_id": row["id"], "section": row["section"], "locator": row.get("locator")}
        effects = []
        for code, name, direction in matches:
            account = chart.get(code)
            if account is None or fold_tr(account.clean_name()) != fold_tr(name.strip()):
                return
            effects.append({"account": code, "name": account.clean_name(),
                            "direction": {"borç": "debit", "alacak": "credit"}[direction],
                            "conditional": "kdv" if "kdv" in fold_tr(name) else "",
                            "source": dict(source, quote=base.strip()), "chart_source": "config/tdhp.json"})
        if not effects or not {"debit", "credit"}.issubset({e["direction"] for e in effects}) or not replacement:
            context.missing_information = ("şablonda ayrıştırılabilir hesap yönleri",)
            return
        unpaid = bool(re.search(r"\b(vadeli|veresiye|odenmedi\w*|odemedi\w*|unpaid|credit)\b", text))
        paid = bool(re.search(r"\b(pesin|nakit|kasadan|bankadan|havale|eft|cash)\b", text))
        context.payment_state = "unpaid" if unpaid and not paid else "paid" if paid and not unpaid else "unspecified"
        if context.payment_state == "paid":
            old, alternatives, direction = replacement.groups()
            options = re.findall(r"(\d{3})\s+(.+?)(?= veya |$)", alternatives)
            cash_effects = []
            for code, name in options:
                account = chart.get(code)
                if account is None or fold_tr(account.clean_name()) != fold_tr(name.strip()):
                    return
                cash_effects.append({"account": code, "name": account.clean_name(),
                    "direction": {"borç": "debit", "alacak": "credit"}[direction],
                    "alternative_group": "payment", "conditional": "payment_method",
                    "source": dict(source, quote="Peşin ödemede" + cash_clause), "chart_source": "config/tdhp.json"})
            if not cash_effects:
                return
            effects = [e for e in effects if e["account"] != old] + cash_effects
        elif context.payment_state == "unspecified":
            context.missing_information = ("ödemenin peşin mi vadeli mi olduğu",)
            # The default credit template must not silently decide payment terms.
            effects = [e for e in effects if e["account"] != replacement.group(1)]
        context.event_type = "inventory_acquisition"
        context.problem_type = PROBLEM_TYPE_TRANSACTION
        context.account_effects = tuple(effects)
        context.affected_accounts = tuple(e["account"] + " " + e["name"] for e in effects)
        context.relevant_concepts = (row["subject"] + " — " + row["section"],)
        context.source_records = (dict(row, text=normative),)

    # ------------------------------------------------------------------
    # 6. DETERMİNİSTİK ARAÇ
    # ------------------------------------------------------------------

    def _needs_deterministic_tool(self, question):
        """Sorunun deterministik bir araç gerektirip gerektirmediğini belirler."""
        return _is_calculation(question)

    # ------------------------------------------------------------------
    # 7. EKSİK BİLGİ
    # ------------------------------------------------------------------

    def _identify_missing_info(self, question):
        """Sorudaki eksik bilgileri belirler."""
        folded = fold_tr(question)
        missing = []

        # Tutar eksik mi?
        if "kac" in folded and not _has_number(question):
            missing.append("tutar")

        # Oran eksik mi?
        if "oran" in folded and not _has_number(question):
            missing.append("oran")

        # Dönem eksik mi?
        if ("hangi" in folded and "donem" in folded) and not _has_year(question):
            missing.append("donem")

        return tuple(missing)

    # ------------------------------------------------------------------
    # 9. ÖNERİLEN STRATEJİ
    # ------------------------------------------------------------------

    def _recommend_strategy(self, context):
        """Reasoning context'e göre önerilen stratejiyi belirler."""
        if context.problem_type == PROBLEM_TYPE_CURRENT_FACT:
            return RESEARCH_FIRST
        if context.problem_type == PROBLEM_TYPE_JOURNAL:
            return ASK_MISSING
        if context.problem_type == PROBLEM_TYPE_TRANSACTION:
            return PRINCIPLE_GROUNDED
        if context.problem_type == PROBLEM_TYPE_DEFINITION:
            return PRINCIPLE_GROUNDED
        if context.problem_type == PROBLEM_TYPE_CALCULATION:
            return ASK_MISSING
        return PRINCIPLE_GROUNDED

    # ------------------------------------------------------------------
    # 10. BİLGİ KAYNAKLARI
    # ------------------------------------------------------------------

    def _determine_sources(self, context):
        """Hangi bilgi kaynaklarının kullanılacağını belirler."""
        sources = []
        if context.relevant_concepts:
            sources.append("learning_store")
        if context.relevant_principle_ids:
            sources.append("principle_registry")
        if context.current_fact_needed:
            sources.append("fact_registry")
            sources.append("research_engine")
        if context.deterministic_tool_needed:
            sources.append("deterministic_tools")
        return tuple(sources)


# ------------------------------------------------------------------
# Yardımcı fonksiyonlar (soru analizi)
# ------------------------------------------------------------------

def _is_calculation(question):
    """Soru matematiksel hesap mı?"""
    import re
    stripped = question.strip()
    if re.fullmatch(r"[\d\s,.+\-*/%()^x×÷]+", stripped):
        return bool(re.search(r"\d", stripped))
    return False


def _is_journal_question(folded):
    """Soru kayıt/yevmiye mi?
    fold_tr sonrası kontrol: 'aldım' → 'aldim', 'hangi hesaba' → 'hangi hesaba'"""
    keywords = ["hangi hesaba", "hangi hesap", "yevmiye", "kayıt", "kaydi",
                "muhasebelestir", "borc mu", "alacak mi"]
    return any(kw in folded for kw in keywords)


def _is_transaction_question(folded):
    """Soru işlem/transaksiyon mı?
    fold_tr sonrası kontrol: 'aldım' → 'aldim' (ı→i dönüşümü).
    Ek varyasyonlar: 'vadeli mal aldım', 'peşin mal aldım', 'müşteriye sattım',
    'borcumu bankadan ödedim', 'müşteriden tahsilat yaptım'."""
    # Other transaction families retain coarse classification only, never account truth.
    return bool(re.search(r"\b(ald[ıi]\w*|satt[ıi]\w*|oded[ıi]\w*|tahsilat)\b", folded))



def _is_definition_question(folded):
    """Soru tanım/kavram mı?"""
    keywords = ["nedir", "ne demek", "tanim", "kavram", "acikla"]
    return any(kw in folded for kw in keywords)


def _is_professional_opinion(folded):
    """Soru mesleki yorum mu?"""
    keywords = ["önerir", "öneri", "tavsiye", "degerlendir", "yorum"]
    return any(kw in folded for kw in keywords)


def _has_number(question):
    """Soru içinde sayı var mı?"""
    import re
    return bool(re.search(r"\d+", question))


def _has_year(question):
    """Soru içinde yıl var mı?"""
    import re
    return bool(re.search(r"(?:19|20)\d{2}", question))
