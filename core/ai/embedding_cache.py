"""KAIZEN — TAM ENTEGRASYON FAZI, Bölüm 2: embedding vektör önbelleği.

`learning/reflection_store.py` ile AYNI ruhta (kendi ayrı .sqlite3 dosyası,
`_connect()`/`closing()` deseni, `db_path=None` -> `data/` altında gerçek dosya, testlerde
geçici dizin) ama tamamen ayrı bir tablodur. Amaç: aynı metin için `OllamaEmbeddingClient`'ı
tekrar tekrar çağırıp soğuk başlangıç/gecikme maliyetine katlanmamak. Anahtar `model +
cache_version + normalize edilmiş metin`dir -- model ya da önbellek şeması değişirse
(cache_version artırılır) eski kayıtlar sessizce yok sayılır, asla hataya düşürmez."""
import json
import hashlib
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from core.text_tr import fold_tr

CACHE_VERSION = 2


class EmbeddingCache:
    def __init__(self, db_path=None, cache_version=CACHE_VERSION):
        root = Path(__file__).resolve().parent.parent.parent
        self.db_path = Path(db_path or root / "data" / "kaizen_embedding_cache.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_version = cache_version
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with closing(self._connect()) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    cache_key TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    cache_version INTEGER NOT NULL,
                    vector TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            connection.commit()

    @staticmethod
    def _key(model, cache_version, text):
        normalized = f"{model}\0{cache_version}\0{fold_tr(text)}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, model, text):
        """Önbellekte varsa float listesi, yoksa/bozuksa None döner -- ASLA raise etmez."""
        key = self._key(model, self.cache_version, text)
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT vector FROM embeddings WHERE cache_key = ?", (key,)
                ).fetchone()
            if row is None:
                return None
            vector = json.loads(row["vector"])
            if not isinstance(vector, list) or not vector:
                return None
            vector = [float(x) for x in vector]
            return vector if all(math.isfinite(x) for x in vector) and any(vector) else None
        except (sqlite3.Error, ValueError, TypeError, OSError):
            return None

    def put(self, model, text, vector):
        """Kaydeder; herhangi bir yazma hatasında sessizce yok sayar (önbellek asla
        cevap akışını kesecek bir hata kaynağı olamaz)."""
        if not vector:
            return
        key = self._key(model, self.cache_version, text)
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO embeddings (cache_key, model, cache_version, vector, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (key, model, self.cache_version, json.dumps(vector), datetime.now(timezone.utc).isoformat()),
                )
                connection.commit()
        except (sqlite3.Error, ValueError, TypeError, OSError):
            pass
