from core.ai.base_provider import BaseAIProvider
from core.hermes_bridge import HermesBridge


class HermesProvider(BaseAIProvider):
    def __init__(self):
        self.hermes = HermesBridge()

    def ask(self, message):
        return self.hermes.ask(message)

    def research(self, message):
        return self.hermes.research(message)

    def research_packet(self, message, trusted_only=True):
        return self.hermes.research_packet(message, trusted_only=trusted_only)

    def collect_sources(self, message):
        return self.hermes.collect_sources(message)
