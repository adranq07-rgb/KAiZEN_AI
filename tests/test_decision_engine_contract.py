"""Decision Engine v1 kontrat testleri (iş emri madde 7 ve 12'nin 10. adımı; başarı kriteri
madde 11.8: "Decision Engine için test edilebilir kontrat oluşmuş").

Bu testler `core/decision.py::DecisionEngine`'in TASARIM SÖZLEŞMESİNİ kilitler -- iş emri
madde 7'nin verdiği örneği BİREBİR doğrular ve her `preferred_route`/`required_confidence`
çiftinin (core/trace.py::ROUTE_CONFIDENCE ile) tutarlı olduğunu garanti eder. `DecisionEngine`
HENÜZ `KaizenBrain`'e bağlı değil (bkz. core/decision.py modül docstring'i) -- bu dosya salt
o bağımsız modülü sınar, gerçek `KaizenBrain.answer()` akışına dokunmaz; dolayısıyla gerçek
data/logs/memory dosyalarına hiç ihtiyaç yok, hiçbir izolasyon gerekmiyor.
"""
from core.decision import Decision, DecisionEngine
from core.trace import PENDING, ROUTE_CONFIDENCE, SUPPORTED, UNKNOWN, VERIFIED


def test_decision_matches_the_work_order_example_sgk_tavan():
    """İş emri madde 7'nin verdiği ÖRNEĞİN kendisi, birebir: '2026 SGK tavanı ne kadar?' için
    intent=sgk_parameter, needs_current_data=true, preferred_route=facts, required_confidence=verified."""
    decision = DecisionEngine().decide("2026 SGK tavanı ne kadar?")
    assert decision.intent == "sgk_parameter"
    assert decision.needs_current_data is True
    assert decision.preferred_route == "facts"
    assert decision.required_confidence == VERIFIED
    print("KAIZEN DECISION ENGINE IS EMRI ORNEGI (SGK TAVANI) TESTI: BASARILI")


def test_decision_never_carries_an_answer_field():
    """Yapısal güvence (iş emri madde 7: 'Decision Engine'in muhasebe sonucunu kendisinin
    üretmesine izin verme. Görevi yalnızca yönlendirmedir.'): `Decision`'ın alan adlarında
    'answer'/'text'/'value'/'result' gibi bir CEVAP alanı asla olmamalı -- yalnız yönlendirme
    bilgisi (intent/route/confidence/reason) taşınabilir."""
    fields = set(Decision.__dataclass_fields__.keys())
    forbidden = {"answer", "text", "value", "result", "response", "output"}
    assert not (fields & forbidden), f"Decision yönlendirme DIŞINDA alan taşıyor: {fields & forbidden}"
    assert fields == {"intent", "preferred_route", "needs_current_data", "required_confidence", "reason"}
    print("KAIZEN DECISION ENGINE YALNIZ YONLENDIRME (CEVAP ALANI YOK) TESTI: BASARILI")


def test_decision_preferred_route_is_always_a_known_kaizen_brain_route():
    """`preferred_route`, core.trace.ROUTE_CONFIDENCE'ın (yani gerçek `KaizenBrain.last_route`
    sözlüğünün) BİLDİĞİ bir rota olmalı -- DecisionEngine kendi uydurma rota adları İCAT ETMEZ."""
    questions = [
        "2026 SGK tavanı ne kadar?", "153 hesap kodu nedir", "2 + 2",
        "Muhasebede dönemsellik ne demek?", "Excel'de düşeyara nasıl kullanılır?",
        "bugün hava nasıl", "2026 KDV oranı nedir?",
        "10.000 TL + %20 KDV ile mal alındı, yevmiye kaydı nedir?",
    ]
    for q in questions:
        decision = DecisionEngine().decide(q)
        assert decision.preferred_route in ROUTE_CONFIDENCE, (
            f"{q!r}: preferred_route={decision.preferred_route!r} core.trace.ROUTE_CONFIDENCE'ta yok"
        )
    print("KAIZEN DECISION ENGINE BILINEN ROTA SOZLUGU TESTI: BASARILI")


def test_decision_exact_tool_intents_require_verified_confidence():
    """Kesin araçlarla (hesap planı/yevmiye/hesap makinesi/aritmetik) yönlendirilen her intent,
    GÜVEN MODELİ ilkesiyle (iş emri madde 8) tutarlı biçimde VERIFIED gerektirmeli -- asla
    daha düşük bir güvenle 'kesin araç kullan ama az güven' gibi çelişkili bir kontrat olmamalı."""
    for question, expected_route in (
        ("153 hesap kodu nedir", "chart"),
        ("2 + 2", "calculator"),
        ("10.000 TL + %20 KDV ile mal alındı, yevmiye kaydı nedir?", "journal"),
    ):
        decision = DecisionEngine().decide(question)
        assert decision.preferred_route == expected_route
        assert decision.required_confidence == VERIFIED
    print("KAIZEN DECISION ENGINE KESIN ARAC = VERIFIED KONTRATI TESTI: BASARILI")


def test_decision_refines_intent_beyond_classifys_four_buckets_without_touching_classify():
    """DecisionEngine, classify()'ın dört kaba kovasını (accounting/office/mathematics/general)
    DEĞİŞTİRMEDEN, ona PARALEL daha granüler bir intent üretiyor -- 'general' sayılan bir SGK
    rejim kodu sorusu bile (bkz. tests/test_classification_failures.py'deki BİLİNEN classify()
    kaçırması) DecisionEngine katmanında doğru 'sgk_parameter' olarak yakalanabiliyor."""
    from core.kaizen_brain import KaizenBrain
    question = "4/a 4/b 4/c nedir, aralarındaki fark ne?"
    assert KaizenBrain.classify(question) == "general"  # classify() hâlâ (bilerek) düzeltilmedi
    decision = DecisionEngine().decide(question)
    assert decision.intent == "sgk_parameter"  # ama DecisionEngine katmanı bunu yakalıyor
    print("KAIZEN DECISION ENGINE GRANULER INTENT (CLASSIFY UZERINE) TESTI: BASARILI")


def test_decision_reason_field_is_always_a_non_empty_string():
    """`reason` -- iş emrinin istediği 'tek bakışta neden' ilkesiyle tutarlı, her kararda dolu
    olmalı (boş/None asla)."""
    for q in ("2 + 2", "bugün hava nasıl", "2026 SGK tavanı ne kadar?"):
        decision = DecisionEngine().decide(q)
        assert isinstance(decision.reason, str) and decision.reason.strip()
    print("KAIZEN DECISION ENGINE REASON ALANI DOLU TESTI: BASARILI")


if __name__ == "__main__":
    test_decision_matches_the_work_order_example_sgk_tavan()
    test_decision_never_carries_an_answer_field()
    test_decision_preferred_route_is_always_a_known_kaizen_brain_route()
    test_decision_exact_tool_intents_require_verified_confidence()
    test_decision_refines_intent_beyond_classifys_four_buckets_without_touching_classify()
    test_decision_reason_field_is_always_a_non_empty_string()
    print("KAIZEN DECISION ENGINE KONTRAT TESTLERI: BASARILI")
