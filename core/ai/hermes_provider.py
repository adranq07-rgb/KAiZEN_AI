from core.ai.base_provider import BaseAIProvider
from core.hermes_bridge import HermesBridge


class HermesProvider(BaseAIProvider):
    def __init__(self, log_dir=None):
        # UAT bulgusu (2026-09-24, tools/research_uat.py Aşama K -- KaizenBrain shadow A/B
        # testi): `HermesBridge()` varsayılan (`log_dir=None`) her zaman GERÇEK
        # `logs/kaizen.log`'a yazar (bkz. core/logger.py::KaizenLogger). Bu, izole/geçici
        # bir provider zinciri kurmak isteyen HERHANGİ bir çağıranın (test veya UAT script'i)
        # `data/`/`logs/` SHA bütünlüğünü İSTEMEDEN bozmasına yol açıyordu -- madde 23
        # ihlali. Düzeltme SADECE ekleyici: `log_dir=None` varsayılanı MEVCUT davranışı
        # (gerçek logs/) BİREBİR korur; yalnızca isteyen çağıran artık kendi izole yolunu
        # geçebilir (bkz. core/ai/provider_factory.py::build_provider).
        self.hermes = HermesBridge(log_dir=log_dir)

    def ask(self, message):
        return self.hermes.ask(message)

    def research(self, message):
        return self.hermes.research(message)

    def research_packet(self, message, trusted_only=True):
        return self.hermes.research_packet(message, trusted_only=trusted_only)

    def collect_sources(self, message):
        return self.hermes.collect_sources(message)
