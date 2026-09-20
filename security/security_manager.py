class SecurityManager:
    def __init__(self):
        self.protected_actions = {
            "delete_file",
            "delete_folder",
            "system_change",
            "install_software",
            "run_admin_command",
        }

    def requires_approval(self, action):
        return action in self.protected_actions

    def check_action(self, action, approved=False):
        if self.requires_approval(action) and not approved:
            return False, "Kazen: Bu islem kullanici onayi gerektiriyor."

        return True, "Kazen: Isleme izin verildi."