import json
from pathlib import Path


class MemoryManager:
    def __init__(self):
        self.memory_file = Path("memory") / "kazen_memory.json"
        self.memory = self._load()

    def _load(self):
        if not self.memory_file.exists():
            return {}

        try:
            with open(self.memory_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self):
        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(self.memory, file, ensure_ascii=False, indent=4)

    def remember(self, key, value):
        self.memory[key] = value
        self.save()

    def recall(self, key):
        return self.memory.get(key)

    def forget(self, key):
        if key in self.memory:
            del self.memory[key]
            self.save()