from security.security_manager import SecurityManager


class ToolManager:
    def __init__(self):
        self.tools = {}
        self.security = SecurityManager()

    def register_tool(self, name, function, action="normal"):
        self.tools[name] = {
            "function": function,
            "action": action
        }

    def has_tool(self, name):
        return name in self.tools

    def run_tool(self, name, *args, approved=False, **kwargs):
        if name not in self.tools:
            return f"Kazen: '{name}' araci bulunamadi."

        tool = self.tools[name]

        allowed, message = self.security.check_action(
            tool["action"],
            approved=approved
        )

        if not allowed:
            return message

        try:
            return tool["function"](*args, **kwargs)
        except Exception as error:
            return f"Kazen: Arac calistirilirken hata olustu: {error}"

    def list_tools(self):
        return list(self.tools.keys())