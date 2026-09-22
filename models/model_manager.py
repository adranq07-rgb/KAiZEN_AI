from models.base_model import BaseModel
from config.config_manager import ConfigManager


class ModelManager:
    def __init__(self):
        self.model = None
        self.config = ConfigManager()
        self.provider = None

    def model_bagla(self, model: BaseModel, provider="local"):
        provider = provider.strip().lower()

        if provider != "local" and not self.config.cloud_allowed():
            return False, f"Kaizen: Bulut modeli engellendi: {provider}"

        self.model = model
        self.provider = provider

        return True, f"Kaizen: Model baglandi: {provider}"

    def cevap_ver(self, mesaj):
        if self.model is None:
            return "Kaizen: Henuz yerel yapay zeka modeli yuklenmedi."

        return self.model.cevap_ver(mesaj)
