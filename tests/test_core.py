from core.engine import KaizenEngine


def test_core():
    kaizen = KaizenEngine()

    assert kaizen.model_manager is not None
    assert kaizen.memory_manager is not None
    assert kaizen.tool_manager is not None
    assert kaizen.security_manager is not None
    assert kaizen.hermes is not None

    print("kaizen CORE TEST: BASARILI")


if __name__ == "__main__":
    test_core()
