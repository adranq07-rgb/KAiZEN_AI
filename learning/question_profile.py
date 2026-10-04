"""KAIZEN — Soru profili: sorunun YAPISINI (kelimelerini değil) çıkarır.

Mali müşavir davranışının ilk adımı: "bu soru NE TÜR bir soru?" -- güncel/yıla bağlı bir
FACT mı (oran, tutar, sınır), kalıcı bir muhasebe prensibi mi, deterministik hesaplanabilir
bir şey mi, yevmiye kaydı mı? Bu modül bu ayrımı YÜZEY kelimelerinden değil YAPISAL
sinyallerden (learning/problem_structure.py + açık yıl + hesap/kayıt kalıpları) çıkarır.
Aynı profil üç yerde kullanılır: (1) deneyim imzası (ReflectionLifecycle), (2) strateji
danışmanı (StrategyAdvisor), (3) trace gözlemi. Profil ASLA bir cevap üretmez ve ASLA bir
FACT taşımaz: yalnız "soru şu yapıda" der.
"""
import re
from dataclasses import dataclass

from core.text_tr import fold_tr
from learning.problem_structure import detect_signals

KIND_CURRENT_FACT = "current_fact"          # yıla/döneme bağlı oran, tutar, sınır, mevzuat sonucu
KIND_PERIOD_PRINCIPLE = "period_principle"  # dönemsellik gerilimi olan KALICI prensip sorusu
KIND_PRINCIPLE = "accounting_principle"     # kalıcı muhasebe kavramı/prensibi
KIND_CALCULATION = "calculation"            # deterministik hesaplanabilir
KIND_JOURNAL = "journal_entry"              # yevmiye kaydı isteniyor
KIND_OFFICE = "office"
KIND_GENERAL = "general"

_YEAR = re.compile(r"(?<![\d.,])(?:19|20)\d{2}(?![\d])")
_JOURNAL = re.compile(r"yevmiye|hangi hesaba|borc.*alacak|kayit|kaydi|muhasebelestir")
_CALC = re.compile(r"\d[\d.,]*\s*(tl|lira|%)|yuzde\s*\d|kac (tl|lira|gun)|hesapla")
_SOURCE_ASK = re.compile(r"kaynak|dayanak|madde|teblig|kanun|resmi gazete|hangi mevzuat")
_MISSING_PARAM = re.compile(r"tutar|matrah|oran|donem|yil")


@dataclass(frozen=True)
class QuestionProfile:
    domain: str
    kind: str
    signals: tuple
    explicit_years: tuple
    asks_for_source: bool
    signature: str          # deneyim eşleşmesinde kullanılan YAPISAL imza (kelime içermez)

    def to_dict(self):
        return {
            "domain": self.domain, "kind": self.kind, "signals": list(self.signals),
            "explicit_years": list(self.explicit_years), "asks_for_source": self.asks_for_source,
            "signature": self.signature,
        }


def explicit_years(question):
    """Soruda AÇIKÇA geçen takvim yılları (ör. 2019, 2026). Yıla bağlı bir FACT sorusunun
    dönemini belirlemenin ilk adımı -- yıl BURADA hard-code edilmez, sorudan okunur."""
    return tuple(sorted({int(y) for y in _YEAR.findall(fold_tr(question))}))


def profile_question(question, domain, needs_current=False):
    folded = fold_tr(question)
    signals = tuple(sorted(detect_signals(question)))
    years = explicit_years(question)
    asks_source = bool(_SOURCE_ASK.search(folded))

    if domain == "office":
        kind = KIND_OFFICE
    elif domain == "mathematics":
        kind = KIND_CALCULATION
    elif domain != "accounting":
        kind = KIND_GENERAL
    elif "RATE_QUERY" in signals or needs_current or years:
        kind = KIND_CURRENT_FACT
    elif "TEMPORAL_MISMATCH" in signals:
        kind = KIND_PERIOD_PRINCIPLE
    elif _JOURNAL.search(folded) and not _CALC.search(folded):
        kind = KIND_JOURNAL
    elif _CALC.search(folded):
        kind = KIND_CALCULATION
    else:
        kind = KIND_PRINCIPLE

    signature = "|".join([domain, kind, "+".join(signals) or "-"])
    return QuestionProfile(domain=domain, kind=kind, signals=signals, explicit_years=years,
                           asks_for_source=asks_source, signature=signature)
