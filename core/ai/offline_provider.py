from core.ai.base_provider import BaseAIProvider

OFFLINE_MESSAGE = "Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod); yalnız yerel hafızadan cevap verebilirim."


class OfflineProvider(BaseAIProvider):
    """Model yokken de çalışan son çare: metin üretmez, Kaizen yerel hafızadan alıntı yaparak cevap verir."""

    is_offline = True

    def ask(self, message):
        return OFFLINE_MESSAGE
