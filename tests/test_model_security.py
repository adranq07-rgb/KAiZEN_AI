from models.model_manager import ModelManager
from models.base_model import BaseModel


def test_model_security():
    manager = ModelManager()

    # Bulut modeli engellenmeli.
    success, message = manager.model_bagla(
        BaseModel(),
        provider="openai"
    )

    assert success is False
    assert manager.model is None

    # Yerel modele izin verilmeli.
    success, message = manager.model_bagla(
        BaseModel(),
        provider="local"
    )

    assert success is True
    assert manager.model is not None
    assert manager.provider == "local"

    print("KAZEN MODEL GUVENLIK TESTI: BASARILI")


if __name__ == "__main__":
    test_model_security()