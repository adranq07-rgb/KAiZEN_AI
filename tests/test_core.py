from core.engine import KazenEngine


def test_core():
    kazen = KazenEngine()

    assert kazen.model_manager is not None
    assert kazen.memory_manager is not None
    assert kazen.tool_manager is not None
    assert kazen.security_manager is not None
    assert kazen.hermes is not None

    print("KAZEN CORE TEST: BASARILI")


if __name__ == "__main__":
    test_core()