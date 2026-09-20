import subprocess
from pathlib import Path


class HermesBridge:
    def __init__(self):
        self.project_dir = Path(__file__).resolve().parent.parent

    def ask(self, message):
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

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300,
            )

            if result.returncode != 0:
                return f"Kazen: Hermes hatasi -> {result.stderr.strip()}"

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            return "Kazen: Hermes zaman asimina ugradi."

        except FileNotFoundError:
            return "Kazen: Hermes bilgisayarda bulunamadi."