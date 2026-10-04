"""KAIZEN — Yeniden kullanılabilir ÇÖZÜM STRATEJİLERİ kataloğu (kapalı küme).

Bir deneyimin "reusable" olabilmesi için stratejisinin BU katalogda bir karşılığı olmalıdır.
Katalog SÜREÇ tarif eder (önce dönemi belirle, kaynağı ara, eşleştir...) -- hiçbir oran,
tutar, yıl, mevzuat sonucu İÇERMEZ. Bu yüzden deneyimden alınan bir ipucu bir FACT'e
dönüşemez: ipucunun metni koddan gelir, kullanıcıdan/araştırmadan/modelden değil.
"""
from learning.question_profile import (
    KIND_CURRENT_FACT, KIND_JOURNAL, KIND_CALCULATION, KIND_PERIOD_PRINCIPLE, KIND_PRINCIPLE,
)

RESEARCH_FIRST = "research_first_official_period"
PERIOD_SEPARATION = "period_separation_principle"
PRINCIPLE_GROUNDED = "principle_grounded_reasoning"
ASK_MISSING = "ask_missing_parameters"

STRATEGIES = {
    RESEARCH_FIRST: {
        "kinds": (KIND_CURRENT_FACT,),
        "triggers_research": True,
        "guide": (
            "Bu soru yıla/döneme bağlı güncel bir parametre soruyor. Süreç: önce sorudaki dönemi "
            "belirle, sonra resmî kaynağı ara, ardından kaynağın dönemini sorudaki dönemle eşleştir "
            "ve mümkünse bağımsız veya resmî ikinci kanıtla doğrula. Kanıt yoksa değer yazma, "
            "'doğrulanamadı' de."
        ),
    },
    PERIOD_SEPARATION: {
        "kinds": (KIND_PERIOD_PRINCIPLE,),
        "triggers_research": False,
        "guide": (
            "Soruda birden fazla dönem/tarih var. Süreç: önce ekonomik olayın AİT OLDUĞU dönemi, "
            "sonra belge/ödeme tarihini ayır; kaydı ait olduğu döneme göre kur ve gerekçeyi "
            "dönemsellik ilkesiyle açıkla."
        ),
    },
    PRINCIPLE_GROUNDED: {
        "kinds": (KIND_PRINCIPLE,),
        "triggers_research": False,
        "guide": (
            "Kavramsal/kalıcı bir muhasebe sorusu. Süreç: soruyu ilgili muhasebe ilkesine bağla, "
            "cevabı yalnız yerel ders/kaynak kanıtıyla gerekçelendir; kanıtta olmayan tutar, "
            "oran veya madde numarası ekleme."
        ),
    },
    ASK_MISSING: {
        "kinds": (KIND_JOURNAL, KIND_CALCULATION),
        "triggers_research": False,
        "guide": (
            "Hesap/kayıt için tutar, oran veya dönem gibi bir parametre eksikse tahmin etme; "
            "eksik parametreyi kullanıcıdan iste, sonra kesin hesap aracıyla çöz."
        ),
    },
}


def strategy_applies_to(strategy_kind, question_kind):
    spec = STRATEGIES.get(strategy_kind)
    return bool(spec) and question_kind in spec["kinds"]
