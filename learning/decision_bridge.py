"""KAIZEN — Learning Brain v1: PrincipleRetrievalResult -> Decision kontratı köprüsü
(iş emri madde 13, "gerekirse ... uyumlu hale getir").

BİLİNÇLİ KAPSAM SINIRI: bu köprü `core/decision.py::DecisionEngine`'e HİÇ dokunmaz ve
`core/kaizen_brain.py::KaizenBrain._answer_core`'a HİÇ bağlanmaz (madde 13: "Decision
Engine'i üretim cevap zincirine tam bağlama"; madde 14: "KaizenBrain'e agresif
entegrasyon yapma"). Yalnız, bir `PrincipleRetrievalResult`'ın `core.decision.Decision`
ile AYNI ALAN ADLARINI taşıyan bir nesneye eşlenebildiğini GÖSTERMEK (observational/
shadow uyumluluk kanıtı) için var; `KaizenBrain.last_route` ASLA "principle_shadow"
değerini almaz -- bu rota yalnız bu köprünün ürettiği Decision nesnelerinde görünür,
gerçek trace/route mekanizmasına hiç karışmaz.

Güven eşlemesi KASITLI OLARAK asla VERIFIED üretmez (madde 16: Principle Layer bir
FACT'i mantıksal çıkarımla asla VERIFIED yapamaz) -- en yükseği SUPPORTED'dır (core/
trace.py'nin GÜVEN MODELİ'yle tutarlı: "bir kaynağı var ama facts/consensus'tan
geçmedi").
"""
from core.decision import Decision
from core.trace import SUPPORTED, UNKNOWN

# core/trace.py::ROUTE_CONFIDENCE'a EKLENEN yeni anahtar (additive) -- KaizenBrain
# BUNU HİÇBİR ZAMAN self.last_route olarak SETlemiyor; yalnız bu köprünün ürettiği
# Decision nesnelerinin `preferred_route`'unun (test_decision_preferred_route_is_
# always_a_known_kaizen_brain_route deseniyle tutarlı biçimde) BİLİNEN bir rota
# sözlüğünde bulunmasını sağlamak için tanımlandı.
PRINCIPLE_SHADOW_ROUTE = "principle_shadow"

_CONFIDENCE_MAP = {
    "HIGH": SUPPORTED,
    "MEDIUM": SUPPORTED,
    "LOW": UNKNOWN,
    "NONE": UNKNOWN,
}


def to_decision(result):
    """`result` (learning.principle_retriever.PrincipleRetrievalResult) ->
    `core.decision.Decision` ile AYNI kontratı taşıyan bir nesne. Yalnız gözlem/
    uyumluluk kanıtı içindir; KaizenBrain'in gerçek yönlendirmesini ETKİLEMEZ."""
    intent = f"principle:{result.selected}" if result.selected else "principle:none"
    return Decision(
        intent=intent,
        preferred_route=PRINCIPLE_SHADOW_ROUTE,
        needs_current_data=result.fact_safety_triggered,
        required_confidence=_CONFIDENCE_MAP.get(result.confidence, UNKNOWN),
        reason=result.reason,
    )
