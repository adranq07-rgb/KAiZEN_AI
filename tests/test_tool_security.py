from security.security_manager import SecurityManager
from tools.tool_manager import ToolManager


def test_tool_security():
    security = SecurityManager()
    assert security.check_action("normal")[0] is True
    assert security.check_action("delete_file")[0] is False
    assert security.check_action("delete_file", approved=True)[0] is True
    assert security.check_action("unexpected", approved=True)[0] is False

    manager = ToolManager()
    calls = []
    manager.register_tool("unsafe", lambda: calls.append(True), action="unexpected")
    assert "engellendi" in manager.run_tool("unsafe", approved=True)
    assert calls == []

    print("KAIZEN ARAC GUVENLIK TESTI: BASARILI")


if __name__ == "__main__":
    test_tool_security()
