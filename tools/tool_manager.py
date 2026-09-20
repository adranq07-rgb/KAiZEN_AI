from security.security_manager import SecurityManager
from core.logger import KaizenLogger


class ToolManager:
    def __init__(self):
        self.tools = {}
        self.security = SecurityManager()
        self.logger = KaizenLogger()

    def register_tool(self, name, function, action="normal"):
        self.tools[name] = {
            "function": function,
            "action": action
        }

        self.logger.info(f"Arac kaydedildi: {name} | action={action}")

    def has_tool(self, name):
        return name in self.tools

    def run_tool(self, name, *args, approved=False, **kwargs):
        if name not in self.tools:
            self.logger.warning(f"Arac bulunamadi: {name}")
            return f"Kaizen: '{name}' araci bulunamadi."

        tool = self.tools[name]

        allowed, message = self.security.check_action(
            tool["action"],
            approved=approved
        )

        if not allowed:
            self.logger.warning(
                f"Arac engellendi: {name} | action={tool['action']}"
            )
            return message

        try:
            self.logger.info(
                f"Arac calistiriliyor: {name} | action={tool['action']}"
            )

            result = tool["function"](*args, **kwargs)

            self.logger.info(f"Arac tamamlandi: {name}")
            return result

        except Exception as error:
            self.logger.error(
                f"Arac hatasi: {name} | {type(error).__name__}: {error}"
            )
            return f"Kaizen: Arac calistirilirken hata olustu: {error}"

    def list_tools(self):
        return list(self.tools.keys())

