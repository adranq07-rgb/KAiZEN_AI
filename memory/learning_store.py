import hashlib
import sqlite3
import re
import math
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from core.text_tr import fold_tr


class LearningStore:
    def __init__(self, db_path=None):
        root = Path(__file__).resolve().parent.parent
        self.db_path = Path(db_path or root / "data" / "kaizen_learning.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with closing(self._connect()) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS learning_chunks (
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    section TEXT,
                    locator TEXT,
                    text TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_learning_subject "
                "ON learning_chunks(domain, subject)"
            )
            connection.execute("""
                CREATE TABLE IF NOT EXISTS learning_chunk_sources (
                    chunk_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    section TEXT,
                    locator TEXT,
                    PRIMARY KEY (chunk_id, source_path, section, locator)
                )
            """)
            connection.execute(
                "CREATE TABLE IF NOT EXISTS learning_meta (key TEXT PRIMARY KEY, value TEXT)"
            )
            connection.commit()

    def get_meta(self, key, default=None):
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT value FROM learning_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key, value):
        with closing(self._connect()) as connection:
            connection.execute("INSERT OR REPLACE INTO learning_meta VALUES (?, ?)", (key, str(value)))
            connection.commit()

    @staticmethod
    def _tokens(value):
        # fold_tr: İ/I/ı ve ş/ğ/ü/ö/ç farkını ortadan kaldırır (ör. "İndirilecek" == "indirilecek",
        # "satıcılar" == "SATICILAR"); hem kayıt hem sorgu aynı biçimde normalleştirilir.
        return set(re.findall(r"[a-z0-9]+", fold_tr(value)))

    def _attach_source(self, connection, chunk_id, source_path, section, locator):
        connection.execute("""
            INSERT OR IGNORE INTO learning_chunk_sources
            (chunk_id, source_path, section, locator) VALUES (?, ?, ?, ?)
        """, (chunk_id, str(source_path), section, locator))

    def add(self, *, domain, subject, source_path, source_type,
            section, locator, text):
        normalized = " ".join(text.split())
        if not normalized:
            return None
        checksum = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        identity = hashlib.sha256(
            f"{source_path}|{section}|{locator}|{checksum}".encode("utf-8")
        ).hexdigest()
        with closing(self._connect()) as connection:
            exact = connection.execute(
                "SELECT id FROM learning_chunks WHERE domain = ? AND checksum = ?",
                (domain, checksum),
            ).fetchone()
            if exact:
                self._attach_source(connection, exact["id"], source_path, section, locator)
                connection.commit()
                return exact["id"]

            new_tokens = self._tokens(normalized)
            if len(new_tokens) >= 20:
                candidates = connection.execute(
                    "SELECT id, text FROM learning_chunks WHERE domain = ?",
                    (domain,),
                ).fetchall()
                for candidate in candidates:
                    old_tokens = self._tokens(candidate["text"])
                    if not old_tokens:
                        continue
                    similarity = len(new_tokens & old_tokens) / len(new_tokens | old_tokens)
                    if similarity >= 0.92:
                        self._attach_source(
                            connection, candidate["id"], source_path, section, locator
                        )
                        connection.commit()
                        return candidate["id"]

            connection.execute("""
                INSERT INTO learning_chunks (
                    id, domain, subject, source_path, source_type,
                    section, locator, text, checksum, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    text=excluded.text,
                    imported_at=excluded.imported_at
            """, (
                identity, domain, subject, str(source_path), source_type,
                section, locator, normalized, checksum,
                datetime.now(timezone.utc).isoformat(),
            ))
            self._attach_source(connection, identity, source_path, section, locator)
            connection.commit()
        return identity

    def remove_by_source(self, source_path, source_type):
        """Belirli bir kaynağın (ör. knowledge/x.json) kendi eklediği parçaları siler; başka kaynaklara dokunmaz."""
        with closing(self._connect()) as connection:
            ids = [r["id"] for r in connection.execute(
                "SELECT id FROM learning_chunks WHERE source_path = ? AND source_type = ?",
                (str(source_path), source_type),
            )]
            for chunk_id in ids:
                connection.execute("DELETE FROM learning_chunk_sources WHERE chunk_id = ?", (chunk_id,))
                connection.execute("DELETE FROM learning_chunks WHERE id = ?", (chunk_id,))
            connection.commit()
        return len(ids)

    def search(self, query, domain=None, limit=8):
        return [row for _, _, row in self.search_scored(query, domain=domain, limit=limit)]

    def search_scored(self, query, domain=None, limit=8):
        """(puan, kapsama, kayıt) üçlüleri döndürür; kapsama = sorgu kelimelerinin kaçının bulunduğu (0-1)."""
        stop_words = {
            "bir", "bu", "ve", "veya", "ile", "icin", "nasil", "nedir", "olan", "olarak",
            "gore", "hangi", "yapilir", "kullanilir", "kullanilabilir", "olur", "edilir",
            "gerekir", "yapilabilir", "midir", "mi", "mu", "ne", "kadar", "kac", "de", "da",
        }
        terms = self._tokens(query) - stop_words
        if not terms:
            return []
        sql = "SELECT * FROM learning_chunks"
        params = []
        if domain:
            sql += " WHERE domain = ?"
            params.append(domain)
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, params).fetchall()
        document_tokens = []
        frequencies = {term: 0 for term in terms}
        for row in rows:
            tokens = self._tokens(f"{row['subject']} {row['section']} {row['text']}")
            document_tokens.append(tokens)
            for term in terms:
                if term in tokens:
                    frequencies[term] += 1

        ranked = []
        normalized_query = fold_tr(query)
        for row, tokens in zip(rows, document_tokens):
            heading = fold_tr(f"{row['subject']} {row['section']}")
            haystack = f"{heading} {fold_tr(row['text'])}"
            score = 0.0
            matched = 0
            for term in terms:
                if term not in tokens:
                    continue
                matched += 1
                inverse_frequency = math.log((len(rows) + 1) / (frequencies[term] + 1)) + 1
                score += inverse_frequency * (2.5 if term in self._tokens(heading) else 1.0)
            coverage = matched / len(terms)
            score *= coverage * coverage
            if normalized_query in haystack:
                score += 8.0
            elif all(term in tokens for term in terms):
                score += 3.0
            if score:
                ranked.append((score, coverage, dict(row)))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return ranked[:limit]

    def stats(self):
        with closing(self._connect()) as connection:
            total = connection.execute("SELECT COUNT(*) FROM learning_chunks").fetchone()[0]
            by_type = connection.execute(
                "SELECT source_type, COUNT(*) FROM learning_chunks GROUP BY source_type"
            ).fetchall()
        return {"total": total, "by_type": dict(by_type)}
