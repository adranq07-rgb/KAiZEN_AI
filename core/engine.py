from models.model_manager import ModelManager
from memory.memory_manager import MemoryManager
from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds
from memory.knowledge_cards import KnowledgeCardStore
from tools.tool_manager import ToolManager
from security.security_manager import SecurityManager
from core.logger import KaizenLogger
from config.config_manager import ConfigManager

from core.ai.provider_manager import ProviderManager
from core.ai.provider_factory import build_provider
from core.commands import CommandHandler
from accounting.accounting_agent import AccountingAgent
from accounting.site_store import SiteStore
from accounting.facts import FactRegistry
from core.kaizen_brain import KaizenBrain


class KaizenEngine:
    def __init__(self):
        self.config = ConfigManager()

        self.name = self.config.get("app", "name", "Kaizen AI")

        self.logger = KaizenLogger()
        self.model_manager = ModelManager()
        self.memory_manager = MemoryManager()
        self.security_manager = SecurityManager()
        self.tool_manager = ToolManager()

        # Kaizen'in kendi hafizasi: ders notlari + ogretilmis bilgiler + toplanan siteler + parametre defteri
        self.learning_store = LearningStore()
        self.seed_report = load_seeds(self.learning_store)
        self.site_store = SiteStore()
        self.facts = FactRegistry(self.site_store.db_path)
        if not self.facts.rows() and self.site_store.count(with_content=True):
            self.facts.rebuild(self.site_store)  # depoda sayfa var ama parametre defteri boşsa süzgeci çalıştır

        # Kendi kendini geliştiren beyin: araştırmadan öğrenilen bilgi kartları (bkz. core/kaizen_brain.py)
        self.cards = KnowledgeCardStore(self.learning_store.db_path)

        # AI provider katmani: Hermes (gecici) -> yerel model -> cevrimdisi; config/Kaizen.json'dan secilir
        self.provider_manager = ProviderManager()
        self.provider_manager.set_provider(build_provider(self.config))
        self.accounting_agent = AccountingAgent(self.provider_manager.provider)
        self.brain = KaizenBrain(
            self.provider_manager,
            self.accounting_agent,
            learning_store=self.learning_store,
            site_store=self.site_store,
            facts=self.facts,
            cards=self.cards,
        )
        self.commands = CommandHandler(self)
        self._register_tools()

        self.logger.info(
            f"Kaizen Engine baslatildi. "
            f"Local First={self.config.local_first()} | "
            f"Cloud Allowed={self.config.cloud_allowed()}"
        )

    def _register_tools(self):
        from tools.office_tools import OFFICE_TOOLS
        for name, function in OFFICE_TOOLS.items():
            self.tool_manager.register_tool(name, function)

    def cevap_ver(self, mesaj):
        if not mesaj.strip():
            self.logger.warning("Bos mesaj alindi.")
            return f"{self.name}: Bos mesaj gonderdin."

        command_answer = self.commands.handle(mesaj)
        if command_answer is not None:
            return command_answer

        return self.brain.answer(mesaj)
