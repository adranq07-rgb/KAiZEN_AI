import json
from pathlib import Path


class LearningMemory:
    def __init__(self, file_path=None):
        if file_path is None:
            project_dir = Path(__file__).resolve().parent.parent
            file_path = project_dir / "data" / "accounting_learning.json"

        self.file_path = Path(file_path)
        self._prepare()
        self.memory = self._load()

    def _prepare(self):
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.file_path.exists():
            self.file_path.write_text(
                "[]",
                encoding="utf-8"
            )

    def _load(self):
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Kaizen ogrenme dosyasi bozuk: {self.file_path}") from error

        if not isinstance(data, list):
            raise ValueError(f"Kaizen ogrenme bicimi gecersiz: {self.file_path}")
        return data

    def add_correction(
        self,
        question,
        wrong_answer,
        correct_answer,
        user_note=None
    ):
        record = {
            "question": question,
            "wrong_answer": wrong_answer,
            "correct_answer": correct_answer,
            "user_note": user_note
        }

        self.memory.append(record)
        self._save()

    def _save(self):
        self.file_path.write_text(
            json.dumps(
                self.memory,
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )

    def get_all(self):
        return self.memory

    def count(self):
        return len(self.memory)
