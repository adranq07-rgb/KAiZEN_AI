import json
from pathlib import Path


class ConfigManager:
    def __init__(self):
        self.project_dir = Path(__file__).resolve().parent.parent
        self.config_file = self.project_dir / "config" / "Kaizen.json"
        self.config = self._load()

    def _load(self):
        if not self.config_file.exists():
            raise FileNotFoundError("Kaizen config dosyasi bulunamadi.")

        with open(self.config_file, "r", encoding="utf-8") as file:
            return json.load(file)

    def get(self, section, key, default=None):
        return self.config.get(section, {}).get(key, default)

    def cloud_allowed(self):
        return self.get("runtime", "cloud_allowed", False)

    def local_first(self):
        return self.get("runtime", "local_first", True)
