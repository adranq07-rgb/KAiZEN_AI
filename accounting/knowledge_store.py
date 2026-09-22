import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path


class AccountingKnowledgeStore:
    def __init__(self, db_path=None):
        root = Path(__file__).resolve().parent.parent
        self.db_path = Path(db_path or root / "data" / "accounting_knowledge.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with closing(self._connect()) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    published_at TEXT,
                    effective_year INTEGER,
                    retrieved_at TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_question ON documents(question)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_published ON documents(published_at)"
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
            if "effective_year" not in columns:
                connection.execute("ALTER TABLE documents ADD COLUMN effective_year INTEGER")
            connection.commit()

    @staticmethod
    def _normalize(value):
        return " ".join(value.casefold().split())

    def save(self, *, question, answer, evidence, source_name, url,
             content, published_at=None, effective_year=None, metadata=None):
        identity = hashlib.sha256(
            f"{url}\n{evidence}".encode("utf-8")
        ).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("""
                INSERT INTO documents (
                    id, question, answer, evidence, source_name, url,
                    published_at, effective_year, retrieved_at, content, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    question=excluded.question,
                    answer=excluded.answer,
                    published_at=excluded.published_at,
                    effective_year=excluded.effective_year,
                    retrieved_at=excluded.retrieved_at,
                    content=excluded.content,
                    metadata_json=excluded.metadata_json
            """, (
                identity, self._normalize(question), answer, evidence,
                source_name, url, published_at, effective_year, now, content,
                json.dumps(metadata or {}, ensure_ascii=False),
            ))
            connection.commit()
        return identity

    def save_page(self, *, title, source_name, url, content,
                  published_at=None, effective_year=None, metadata=None):
        return self.save(
            question=title or url,
            answer="",
            evidence="",
            source_name=source_name,
            url=url,
            content=content,
            published_at=published_at,
            effective_year=effective_year,
            metadata={**(metadata or {}), "record_type": "source_page"},
        )

    def find_recent(self, question, earliest_date):
        normalized = self._normalize(question)
        with closing(self._connect()) as connection:
            row = connection.execute("""
                SELECT * FROM documents
                WHERE question = ?
                  AND ((effective_year IS NOT NULL AND effective_year >= ?)
                       OR (published_at IS NOT NULL AND published_at >= ?))
                ORDER BY published_at DESC, retrieved_at DESC
                LIMIT 1
            """, (normalized, earliest_date.year, earliest_date.isoformat())).fetchone()
        return dict(row) if row else None

    def count(self):
        with closing(self._connect()) as connection:
            return connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def search_latest(self, query, limit=5):
        terms = {term for term in self._normalize(query).split() if len(term) >= 3}
        if not terms:
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute("""
                SELECT * FROM documents
                ORDER BY COALESCE(effective_year, 0) DESC,
                         COALESCE(published_at, '') DESC,
                         retrieved_at DESC
                LIMIT 500
            """).fetchall()
        ranked = []
        for row in rows:
            if not row["content"]:
                continue
            haystack = self._normalize(
                f"{row['question']} {row['answer']} {row['content']}"
            )
            score = sum(1 for term in terms if term in haystack)
            if score:
                ranked.append((score, dict(row)))
        ranked.sort(
            key=lambda item: (
                item[0], item[1].get("effective_year") or 0,
                item[1].get("published_at") or "",
            ),
            reverse=True,
        )
        return [row for _, row in ranked[:limit]]
