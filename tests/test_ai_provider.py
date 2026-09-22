from core.ai.provider_manager import ProviderManager


class FakeProvider:
    def ask(self, message):
        return f"YANIT:{message}"


def test_ai_provider():
    manager = ProviderManager()
    assert "provider baglanmadi" in manager.ask("Merhaba")
    manager.set_provider(FakeProvider())
    assert manager.ask("Merhaba") == "YANIT:Merhaba"

    print("KAIZEN SAGLAYICI TESTI: BASARILI")


if __name__ == "__main__":
    test_ai_provider()
