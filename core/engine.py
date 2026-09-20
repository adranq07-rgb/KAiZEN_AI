from models.model_manager import ModelManager
from memory.memory_manager import MemoryManager
from tools.tool_manager import ToolManager
from security.security_manager import SecurityManager
from core.hermes_bridge import HermesBridge
from core.logger import KazenLogger


class KazenEngine:
    def __init__(self):
        self.name = "Kazen"

        self.logger = KazenLogger()
        self.model_manager = ModelManager()
        self.memory_manager = MemoryManager()
        self.security_manager = SecurityManager()
        self.tool_manager = ToolManager()
        self.hermes = HermesBridge()

        self.logger.info("Kazen Engine baslatildi.")

    def cevap_ver(self, mesaj):
        if not mesaj.strip():
            self.logger.warning("Bos mesaj alindi.")
            return f"{self.name}: Bos mesaj gonderdin."

        return self.model_manager.cevap_ver(mesaj)