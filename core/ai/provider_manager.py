from core.ai.base_provider import BaseAIProvider


class ProviderManager:
    def __init__(self):
        self.provider = None

    def set_provider(self, provider: BaseAIProvider):
        self.provider = provider

    def ask(self, message):
        if self.provider is None:
            return "Kaizen: Henuz bir AI provider baglanmadi."

        return self.provider.ask(message)