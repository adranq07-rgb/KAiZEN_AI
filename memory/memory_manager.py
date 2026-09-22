import json
from pathlib import Path


class MemoryManager:
    def __init__(self, file_path=None):
        self.memory_file = Path(file_path) if file_path else Path(__file__).resolve().parent / "kaizen_memory.json"
        self.memory = self._load()

    def _load(self):
        if not self.memory_file.exists():
            return {}

        with open(self.memory_file, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError as error:
                raise ValueError(f"Kaizen hafiza dosyasi bozuk: {self.memory_file}") from error

        if not isinstance(data, dict):
            raise ValueError(f"Kaizen hafiza bicimi gecersiz: {self.memory_file}")
        return data

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
