"""Read-only empty view when a knowledge database cannot be opened.

Writes fail explicitly; this must never pretend that user teaching was saved.
"""
class UnavailableLearningStore:
    db_path = None

    def search(self, *args, **kwargs):
        return []

    def search_scored(self, *args, **kwargs):
        return []

    def stats(self):
        return {"total": 0, "by_type": {}, "available": False}

    def add(self, *args, **kwargs):
        raise OSError("Bilgi deposu kullanılamıyor; kayıt yapılmadı.")
