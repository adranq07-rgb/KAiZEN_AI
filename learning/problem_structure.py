"""KAIZEN — Learning Brain v1: hafif problem-structure temsili (iş emri madde 7).

"Aralık ayında kullanılan elektrik faturası ocakta geldi" ile "Aralık hizmetine
ilişkin ödeme şubatta yapıldı" farklı kelimeler taşır ama İKİSİ DE "ekonomik olayın
ait olduğu dönem" ile "belge/ödeme tarihi" arasındaki AYRIMA (yapısal role) dayanır.
Bu modül, tam bir semantic planner YAZMADAN (madde 7, açıkça yasak), sorunun YÜZEY
kelimelerinden çok ROLÜNÜ yakalayan küçük, denetlenebilir kalıp (regex/deyim) tabanlı
sinyaller üretir -- ör. "iki farklı ay adı birlikte geçiyor" (TEMPORAL_MISMATCH),
"hangi hesaba/sınıfa" (ACCOUNT_CLASS_QUERY), "hangi tarafa" (DIRECTION_QUERY) gibi.

Her sinyal KASITLI olarak GENELLENEBİLİR bir Türkçe muhasebe deyimi/kalıbıdır --
belirli bir örneğin (elektrik faturası, üretim makinesi...) İSİM/NESNE kelimesine
DEĞİL, sorunun YAPISINA bağlıdır; böylece madde 9'un ("kelime eşleşmesine düşme")
tam tersini KASITLI olarak sergiler.

learning/principle_retriever.py bu sinyalleri, memory/principle_registry.py'deki
her ilkenin `problem_structure.primary_signal`/`veto_signals` alanlarıyla eşleştirir.
"""
import re

from core.text_tr import fold_tr

_MONTHS = (
    "ocak", "subat", "mart", "nisan", "mayis", "haziran", "temmuz", "agustos",
    "eylul", "ekim", "kasim", "aralik",
)
_MONTH_PATTERN = re.compile(r"\b(" + "|".join(_MONTHS) + r")\b")

_ACCOUNT_CLASS_PATTERN = re.compile(
    r"hangi (ana )?(hesap )?(sinifa|sinifina|grupta|gruba|hesaba|hesap kod)"
)
_DIRECTION_PATTERN = re.compile(r"hangi tarafa|borc mu.*alacak mi|hangi taraf hareket")
_VALUATION_PATTERN = re.compile(r"piyasa degeri")
_BENEFIT_SPREAD_PATTERN = re.compile(r"yillara yayarak|tek seferde|faydali omur")
_LEGAL_ECONOMIC_PATTERN = re.compile(r"kimin varligi|kimin aktifinde|mulkiyet")
_STATUS_PATTERN = re.compile(r"hangi statude|hangi sigortalilik statusunde")
_RATE_PATTERN = re.compile(r"\boran(i|inin|inda)?\b.*\b(nedir|kac|ne kadar)\b|stopaj orani|kdv orani|vergi orani")

# Bir metinde iki (veya daha fazla) FARKLI para tutarı (X TL) geçiyor mu -- maliyet
# (elde etme bedeli) ile güncel piyasa değeri arasındaki YAPISAL gerilimin bir parçası.
_AMOUNT_PATTERN = re.compile(r"\d[\d.,]*\s*tl")


def _distinct_months(folded_text):
    return set(_MONTH_PATTERN.findall(folded_text))


def detect_signals(question):
    """Soru metninden gözlemlenebilir yapısal sinyal kimliklerinin KÜMESİNİ döner.

    Birden fazla sinyal AYNI ANDA ateşleyebilir (ör. hem TEMPORAL_MISMATCH hem
    ACCOUNT_CLASS_QUERY) -- bu KASITLI: iki ilke birden aday olur, seçim
    learning/principle_retriever.py'nin skorlama+veto mantığına kalır (madde 18:
    "birden fazla aday" testi tam olarak bu durumu sınar)."""
    folded = fold_tr(question)
    signals = set()
    if len(_distinct_months(folded)) >= 2:
        signals.add("TEMPORAL_MISMATCH")
    if _ACCOUNT_CLASS_PATTERN.search(folded):
        signals.add("ACCOUNT_CLASS_QUERY")
    if _DIRECTION_PATTERN.search(folded):
        signals.add("DIRECTION_QUERY")
    if _VALUATION_PATTERN.search(folded) and len(_AMOUNT_PATTERN.findall(folded)) >= 2:
        signals.add("VALUATION_VS_COST_QUERY")
    if _BENEFIT_SPREAD_PATTERN.search(folded):
        signals.add("BENEFIT_SPREAD_QUERY")
    if _LEGAL_ECONOMIC_PATTERN.search(folded) and "sozlesme" in folded:
        signals.add("LEGAL_VS_ECONOMIC_QUERY")
    if _STATUS_PATTERN.search(folded):
        signals.add("STATUS_CLASSIFICATION_QUERY")
    if _RATE_PATTERN.search(folded):
        # FACT güvenlik sinyali (madde 16): bir "oran nedir/kaç" kalıbı -- Principle
        # Layer bunu ASLA bir ilke ile "VERIFIED" yapmaya çalışmamalı.
        signals.add("RATE_QUERY")
    return signals
