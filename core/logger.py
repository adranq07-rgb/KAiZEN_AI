from datetime import datetime
from pathlib import Path


class KaizenLogger:
    def __init__(self):
        self.project_dir = Path(__file__).resolve().parent.parent
        self.log_dir = self.project_dir / "logs"
        self.log_file = self.log_dir / "kaizen.log"

        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, level, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        line = f"[{timestamp}] [{level.upper()}] {message}\n"

        with open(self.log_file, "a", encoding="utf-8") as file:
            file.write(line)

    def info(self, message):
        self.log("INFO", message)

    def warning(self, message):
        self.log("WARNING", message)

    def error(self, message):
        self.log("ERROR", message)
