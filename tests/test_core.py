from core.engine import KaizenEngine


def test_core():
    kaizen = KaizenEngine()

    assert kaizen.model_manager is not None
    assert kaizen.memory_manager is not None
    assert kaizen.tool_manager is not None
    assert kaizen.security_manager is not None

    assert kaizen.provider_manager is not None
    assert kaizen.provider_manager.provider is not None
    assert kaizen.accounting_agent is not None
    assert kaizen.cevap_ver("muhasebe: ") == "Kaizen: Muhasebe sorusu bos olamaz."

    kaizen.brain.answer = lambda message: f"BEYIN:{message}"

    assert kaizen.cevap_ver("Merhaba") == "BEYIN:Merhaba"
    assert kaizen.cevap_ver("muhasebe: Fatura kaydi nedir?") == "BEYIN:muhasebe: Fatura kaydi nedir?"

    print("KAIZEN CORE TEST: BASARILI")


if __name__ == "__main__":
    test_core()
