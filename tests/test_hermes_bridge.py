from core.hermes_bridge import HermesBridge


def test_hermes_bridge_lock():
    bridge = HermesBridge()

    assert bridge.is_ready() is False

    result = bridge.ask("Bu mesaj Hermes'e gitmemeli.")

    assert "Yerel yapay zeka modeli henuz yapilandirilmadi" in result

    print("KAZEN HERMES GUVENLIK TESTI: BASARILI")


if __name__ == "__main__":
    test_hermes_bridge_lock()