from models.base_model import BaseModel


class ModelManager:
    def __init__(self):
        self.model = None

    def model_bagla(self, model: BaseModel):
        self.model = model

    def cevap_ver(self, mesaj):
        if self.model is None:
            return "Kazen: Henuz yerel yapay zeka modeli yuklenmedi."

        return self.model.cevap_ver(mesaj)