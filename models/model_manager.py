from models.base_model import BaseModel
from config.config_manager import ConfigManager


class ModelManager:
    def __init__(self):
        self.model = None
        self.config = ConfigManager()
        self.provider = None

    def model_bagla(self, model: BaseModel, provider="local"):
        cloud_providers = {
            "openai",
            "anthropic",
            "claude",
            "openrouter",
            "gemini",
            "mistral_api",
        }

        provider = provider.lower()

        if provider in cloud_providers and not self.config.cloud_allowed():
            return False, f"Kazen: Bulut modeli engellendi: {provider}"

        self.model = model
        self.provider = provider

        return True, f"Kazen: Model baglandi: {provider}"

    def cevap_ver(self, mesaj):
        if self.model is None:
            return "Kazen: Henuz yerel yapay zeka modeli yuklenmedi."

        return self.model.cevap_ver(mesaj)