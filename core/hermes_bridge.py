import subprocess
from pathlib import Path

from config.config_manager import ConfigManager
from core.logger import KazenLogger


class HermesBridge:
    def __init__(self):
        self.project_dir = Path(__file__).resolve().parent.parent
        self.config = ConfigManager()
        self.logger = KazenLogger()

    def is_ready(self):
        provider = self.config.get("model", "provider", "not_configured")

        if provider == "not_configured":
            return False

        if not self.config.cloud_allowed() and provider != "local":
            return False

        return True

    def ask(self, message):
        if not self.is_ready():
            self.logger.warning(
                "Hermes cagrisi engellendi: yerel model hazir degil."
            )
            return (
                "Kazen: Hermes su anda calistirilmadi. "
                "Yerel yapay zeka modeli henuz yapilandirilmadi."
            )

        command = [
            "hermes",
            "chat",
            "-q",
            message,
            "--oneshot",
            "-Q",
            "--in",
            str(self.project_dir),
            "--source",
            "tool",
        ]

        self.logger.info("Hermes cagrisi baslatildi.")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300,
            )

            if result.returncode != 0:
                self.logger.error(
                    f"Hermes hata kodu: {result.returncode}"
                )
                return f"Kazen: Hermes hatasi -> {result.stderr.strip()}"

            self.logger.info("Hermes cagrisi tamamlandi.")
            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            self.logger.error("Hermes zaman asimina ugradi.")
            return "Kazen: Hermes zaman asimina ugradi."

        except FileNotFoundError:
            self.logger.error("Hermes bilgisayarda bulunamadi.")
            return "Kazen: Hermes bilgisayarda bulunamadi."