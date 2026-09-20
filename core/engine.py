from models.model_manager import ModelManager
from memory.memory_manager import MemoryManager
from tools.tool_manager import ToolManager
from security.security_manager import SecurityManager
from core.hermes_bridge import HermesBridge
from core.logger import KaizenLogger
from config.config_manager import ConfigManager


class KaizenEngine:
    def __init__(self):
        self.config = ConfigManager()

        self.name = self.config.get("app", "name", "Kaizen AI")

        self.logger = KaizenLogger()
        self.model_manager = ModelManager()
        self.memory_manager = MemoryManager()
        self.security_manager = SecurityManager()
        self.tool_manager = ToolManager()
        self.hermes = HermesBridge()

        self.logger.info(
            f"Kaizen Engine baslatildi. "
            f"Local First={self.config.local_first()} | "
            f"Cloud Allowed={self.config.cloud_allowed()}"
        )

    def cevap_ver(self, mesaj):
        if not mesaj.strip():
            self.logger.warning("Bos mesaj alindi.")
            return f"{self.name}: Bos mesaj gonderdin."

        return self.model_manager.cevap_ver(mesaj)
