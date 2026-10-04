"""KAIZEN Research Engine — Research Trigger (İş Emri #2 madde 9, 32-33).

KARAR (madde 32): `core/decision.py::DecisionEngine` Faz 1 denetiminde tamamen ölü/
izole bulundu (bkz. docs/KAIZEN_RUNTIME_ARCHITECTURE.md §5) -- sıfırdan başlanacağı
teyit edildi. Bu modül `needs_research`/`needs_exact_tool`/`needs_fact`/`needs_memory`
bayraklarından yalnız İLKİNİ (madde 7'nin konusu olan) üretir; diğer üçü zaten bugünkü
`KaizenBrain._answer_core` sırasının (correction→arithmetic→exact_tools→facts→
memory_grounded) KENDİSİ tarafından, kod akışıyla (ayrı bayraklara ihtiyaç duymadan)
sağlanıyor -- burada YENİDEN İCAT EDİLMEDİ.

TASARIM (madde 61: "büyük yeniden yazım yok", tekrar sınıflandırma yazma yasağı):
`KaizenBrain.classify()` ve `KaizenBrain.needs_current_research()` (core/kaizen_brain.py)
ZATEN var ve üretimde kullanılıyor -- bu modül onları ÇAĞIRIR, yeniden yazmaz.

Gerçek entegrasyon noktasında (Faz 28, docs/RESEARCH_ENGINE.md §5) bu fonksiyon
`_from_memory()` BAŞARISIZ OLDUKTAN SONRA çağrılacak -- yani `local_evidence_found`
o noktada zaten kesin olarak bilinir (False). Bu modülün kendi test paketinde
(madde 33, izole/tek başına test edilebilirlik için) `local_evidence_found` açıkça
parametre olarak verilir; `None` bırakılırsa yalnız soru metninden (madde 9'un istediği
"ilk sinyal") en iyi tahmin üretilir -- bu, GERÇEK zincirde asla tek başına karar
vermez, yalnızca standalone/madde-33 testleri için bir kestirimdir."""
from core.kaizen_brain import KaizenBrain

# Research Engine yalnız muhasebe/SGK alanında anlamlıdır (mimari karar, docs/
# RESEARCH_ENGINE.md §5) -- genel sohbet/matematik/ofis sorularında hiç tetiklenmez.
_RESEARCHABLE_DOMAINS = ("accounting",)


def needs_research(question, local_evidence_found=None):
    """Research Engine bu soru için tetiklenmeli mi?

    - domain != 'accounting' -> HAYIR (mimari karar, madde 28: yalnız muhasebe/SGK dalı).
    - local_evidence_found is True -> HAYIR (`_from_memory` zaten yeterli kanıt buldu,
      madde 28: research yalnız yerel hafıza YETERSİZ kaldığında devreye girer).
    - local_evidence_found is False -> EVET (yerel hafızada hiç kanıt yok, başka çare yok).
    - local_evidence_found is None (yalnız standalone/madde-33 test modu) ->
      `KaizenBrain.needs_current_research()` sinyaline bakılır (güncel yıl/oran/mevzuat
      kelimesi var mı) -- bu, henüz `_from_memory` çalıştırılmadan yapılan bir KESTİRİMDİR,
      gerçek üretim kararı DEĞİLDİR (orada local_evidence_found her zaman açıkça bilinir)."""
    domain = KaizenBrain.classify(question)
    if domain not in _RESEARCHABLE_DOMAINS:
        return False
    if local_evidence_found is True:
        return False
    if local_evidence_found is False:
        return True
    return bool(KaizenBrain.needs_current_research(question))


def domain_of(question):
    """Kolaylık sarmalayıcı -- test/rapor kodunun `core.kaizen_brain` içine ayrıca
    import eklemesini gerektirmesin diye (tek gerçek kaynak yine KaizenBrain.classify)."""
    return KaizenBrain.classify(question)
