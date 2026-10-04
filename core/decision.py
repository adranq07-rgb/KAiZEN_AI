"""Decision Engine v1 -- TASARIM + TEST EDİLEBİLİR KONTRAT (iş emri madde 7 ve 12'nin
10. adımı).

DURUM (önemli): Bu modül HENÜZ `KaizenBrain`'e bağlanmadı. İş emri madde 7'nin dediği gibi
"mümkünse önce tasarla ve test kontratını oluştur" -- bu, o tasarımın KENDİSİ: bağımsız,
kendi başına test edilen, sıfır regresyon riski taşıyan bir modül. `_answer_core`'a
bağlanıp bağlanmayacağına (ve nasıl) kullanıcı onayıyla, AYRI bir fazda karar verilecek
(iş emri madde 1: "Büyük refactor yapılmayacak", madde 12: adım 10 TASARIM, adım 11 yalnız
KANITLANMIŞ noktalı düzeltmeler -- bu ikisi kasıtlı olarak ayrı tutuluyor).

GÖREV SINIRI (iş emri madde 7, son cümle): "Decision Engine'in muhasebe sonucunu kendisinin
üretmesine izin verme. Görevi yalnızca yönlendirmedir." Bu yüzden `Decision` sınıfında bir
"answer"/"text"/"value" alanı YOK ve olmayacak -- yalnız YÖNLENDİRME bilgisi taşır
(`tests/test_decision_engine_contract.py::test_decision_never_carries_an_answer_field` bunu
yapısal olarak, alan adlarını tarayarak zorluyor). Gerçek cevabı üretmek hâlâ TAMAMEN
`KaizenBrain`/`BrainManager`/`accounting/*` katmanlarının işi.

Kontrat (iş emri madde 7'de verilen örnekle birebir):

    >>> DecisionEngine().decide("2026 SGK tavanı ne kadar?")
    Decision(intent='sgk_parameter', preferred_route='facts', needs_current_data=True,
             required_confidence='VERIFIED', reason='...')

Alanlar:
  * intent              -- `KaizenBrain.classify()`'in 4 kaba kovasından (accounting/office/
                            mathematics/general) DAHA GRANÜLER bir sınıflandırma (aşağıya
                            bakınız). classify()'ı DEĞİŞTİRMEZ, ona PARALEL, salt-okunur bir
                            ek katmandır (iş emri madde 4: "Henüz bunu LLM classifier ile
                            değiştirme" -- burada da değiştirmiyoruz, yalnız ayrı bir kural
                            tabanlı katman EKLİYORUZ, hâlâ LLM değil).
  * preferred_route      -- `KaizenBrain.last_route` ile AYNI sözlükten (core/trace.py
                            ROUTE_CONFIDENCE anahtarları) bir öneri; KaizenBrain'in GERÇEKTE
                            hangi yolu izleyeceğinin garantisi değildir (bu hâlâ mevcut
                            `_answer_core` sırasına bağlı) -- yalnız bir ÖN TAHMİN/yönlendirme.
  * needs_current_data   -- `KaizenBrain.needs_current_research()`'e devrediyor (bkz. aşağıdaki
                            BİLİNEN SINIRLAMA notu -- düzeltilmedi, yalnız devraldı).
  * required_confidence  -- core.trace sözlüğünden (VERIFIED/SUPPORTED/PENDING/UNKNOWN) bu
                            intent için KABUL EDİLEBİLİR asgari güven düzeyi -- örn. bir
                            SGK/vergi PARAMETRESİ sorusu asla UNKNOWN/PENDING bir cevapla
                            "kesinmiş gibi" sunulmamalı, bu yüzden VERIFIED istenir.
  * reason               -- tek cümlelik, insan-okunur gerekçe (hangi kural tetiklendi).

BİLİNEN SINIRLAMA (bilerek devralındı, düzeltilmedi): `needs_current_data`,
`tests/test_retrieval_failures.py::test_retrieval_needs_current_research_false_positive_...`
testinde kanıtlanan `needs_current_research()`'ün "oran" gibi genel kelimelerde yanlış
pozitif verme sorununu MİRAS alıyor. Bu modül o hatayı DÜZELTMİYOR -- yalnız mevcut
`KaizenBrain`'in kullandığı AYNI fonksiyonu çağırarak tutarlı kalıyor. Düzeltme, iş emri
madde 11 kapsamında (kanıtlanmış, en küçük değişiklik) ayrıca değerlendirilecek.
"""
import re
from dataclasses import dataclass

from core.kaizen_brain import KaizenBrain
from core.text_tr import fold_tr
from core.trace import PENDING, SUPPORTED, UNKNOWN, VERIFIED

# Granüler intent sabitleri. Hepsi `KaizenBrain.classify()`'in DÖRT kovasından birine
# (accounting/office/mathematics/general) eşlenir (bkz. `_BASE_INTENT`); yalnız muhasebe
# sorularını, yönlendirme kararı farklılaşacak kadar ayırt edici alt-türlere bölerler.
INTENT_ACCOUNT_CODE = "account_code"
INTENT_SGK_PARAMETER = "sgk_parameter"
INTENT_TAX_PARAMETER = "tax_parameter"
INTENT_ACCOUNTING_CONCEPT = "accounting_concept"
INTENT_JOURNAL_ENTRY = "journal_entry"
INTENT_ARITHMETIC = "arithmetic"
INTENT_OFFICE = "office"
INTENT_GENERAL = "general"

# preferred_route için: core.trace.ROUTE_CONFIDENCE ile AYNI sözlükten -- yeni bir rota adı
# İCAT EDİLMİYOR, yalnız mevcut `KaizenBrain.last_route` sözlüğünden seçim yapılıyor.
_ROUTE_FOR_INTENT = {
    INTENT_ACCOUNT_CODE: "chart",
    INTENT_SGK_PARAMETER: "facts",
    INTENT_TAX_PARAMETER: "facts",
    INTENT_JOURNAL_ENTRY: "journal",
    INTENT_ARITHMETIC: "calculator",
    INTENT_ACCOUNTING_CONCEPT: "memory_extractive",
    INTENT_OFFICE: "memory_extractive",
    INTENT_GENERAL: "provider",
}

_REQUIRED_CONFIDENCE_FOR_INTENT = {
    INTENT_ACCOUNT_CODE: VERIFIED,
    INTENT_SGK_PARAMETER: VERIFIED,
    INTENT_TAX_PARAMETER: VERIFIED,
    INTENT_JOURNAL_ENTRY: VERIFIED,
    INTENT_ARITHMETIC: VERIFIED,
    INTENT_ACCOUNTING_CONCEPT: SUPPORTED,
    INTENT_OFFICE: SUPPORTED,
    INTENT_GENERAL: UNKNOWN,
}

# Bilinen classify() kaçırmalarını (bkz. tests/test_classification_failures.py) telafi etmek
# İÇİN DEĞİL -- classify()'a hiç dokunmuyoruz -- yalnız DAHA GRANÜLER bir intent vermek için.
# Bilinçli olarak dar: yalnız kanıtlanmış, somut örüntüler (SGK rejim kodu, çıplak 3 haneli
# hesap kodu bağlamı).
_SGK_REGIME_CODE = re.compile(r"\b4[\s/]?[abc]\b")
_ACCOUNT_CODE_CONTEXT = re.compile(r"\b\d{3}\b.*\bhesap")
_JOURNAL_HINT = ("yevmiye kaydi", "kayit nedir", "kaydi nedir", "muhasebe kaydi")
# Parametre (yıllık oran/tavan/taban/tarife/sınır) sorularını kavramsal muhasebe sorularından
# ayırmak için: iş emri madde 7'nin verdiği örneğin ('2026 SGK tavanı ne kadar?') doğru intent
# üretmesi için gerekli -- "sgk"/vergi kelimesi + bir parametre ipucu birlikte geçiyorsa.
_PARAMETER_HINTS = ("tavan", "taban", "tarife", "oran", "asgari ucret", "limit", "sinir", "haddi")
_TAX_WORDS = ("vergi", "kdv", "stopaj", "harc", "damga")


@dataclass(frozen=True)
class Decision:
    intent: str
    preferred_route: str
    needs_current_data: bool
    required_confidence: str
    reason: str


class DecisionEngine:
    """Yalnız YÖNLENDİRME kararı üretir -- hiçbir muhasebe/matematik SONUCU hesaplamaz,
    hiçbir metin cevabı döndürmez. `decide(question) -> Decision`."""

    @staticmethod
    def _refine_intent(question, base_intent):
        folded = fold_tr(question)
        if base_intent == "mathematics":
            return INTENT_ARITHMETIC
        if base_intent == "office":
            return INTENT_OFFICE
        has_parameter_hint = any(hint in folded for hint in _PARAMETER_HINTS)
        if base_intent == "accounting":
            if _SGK_REGIME_CODE.search(folded) or ("sgk" in folded and has_parameter_hint):
                return INTENT_SGK_PARAMETER
            if any(w in folded for w in _TAX_WORDS) and has_parameter_hint:
                return INTENT_TAX_PARAMETER
            if any(hint in folded for hint in _JOURNAL_HINT):
                return INTENT_JOURNAL_ENTRY
            if _ACCOUNT_CODE_CONTEXT.search(folded):
                return INTENT_ACCOUNT_CODE
            return INTENT_ACCOUNTING_CONCEPT
        # base_intent == "general": yine de SGK/hesap kodu örüntüsü içerebilir (bkz.
        # tests/test_classification_failures.py -- classify()'ın kaçırdığı, bilinen durumlar).
        if _SGK_REGIME_CODE.search(folded) or ("sgk" in folded and has_parameter_hint):
            return INTENT_SGK_PARAMETER
        if _ACCOUNT_CODE_CONTEXT.search(folded):
            return INTENT_ACCOUNT_CODE
        return INTENT_GENERAL

    def decide(self, question):
        base_intent = KaizenBrain.classify(question)
        intent = self._refine_intent(question, base_intent)
        needs_current = KaizenBrain.needs_current_research(question)
        route = _ROUTE_FOR_INTENT[intent]
        confidence = _REQUIRED_CONFIDENCE_FOR_INTENT[intent]
        reason = (
            f"classify()='{base_intent}' + kural tabanlı iyileştirme -> intent='{intent}' "
            f"(bkz. core/decision.py::DecisionEngine._refine_intent); needs_current_data="
            f"KaizenBrain.needs_current_research() sonucu."
        )
        return Decision(
            intent=intent, preferred_route=route, needs_current_data=needs_current,
            required_confidence=confidence, reason=reason,
        )
