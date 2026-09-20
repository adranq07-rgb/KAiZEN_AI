from models.model_manager import ModelManager
from memory.memory_manager import MemoryManager
from tools.tool_manager import ToolManager
from security.security_manager import SecurityManager
from core.hermes_bridge import HermesBridge


class KazenEngine:
    def __init__(self):
        self.name = "Kazen"

        self.model_manager = ModelManager()
        self.memory_manager = MemoryManager()
        self.security_manager = SecurityManager()
        self.tool_manager = ToolManager()
        self.hermes = HermesBridge()

    def cevap_ver(self, mesaj):
        if not mesaj.strip():
            return f"{self.name}: Bos mesaj gonderdin."

        return self.model_manager.cevap_ver(mesaj)