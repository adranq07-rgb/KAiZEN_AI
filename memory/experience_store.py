import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class ExperienceStore:
    """Kaizen'e ait görev ve araç kayıtlarını yerel olarak saklar."""

    SCHEMA_VERSION = 1
    KINDS = {"conversation", "tool_result", "source", "correction", "skill"}
    STATUSES = {"success", "failure", "unverified"}

    def __init__(self, database_path=None):
        project_dir = Path(__file__).resolve().parent.parent
        self.database_path = Path(database_path) if database_path else project_dir / "data" / "kaizen_experiences.sqlite3"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS experiences (
                        id TEXT PRIMARY KEY,
                        schema_version INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        status TEXT NOT NULL,
                        source_refs TEXT NOT NULL,
                        payload TEXT NOT NULL
                    )"""
                )

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def add(self, kind, provider, status, payload, source_refs=None):
        if kind not in self.KINDS:
            raise ValueError("Bilinmeyen kayit turu")
        if status not in self.STATUSES:
            raise ValueError("Bilinmeyen kayit durumu")
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("Saglayici adi gerekli")
        if not isinstance(payload, dict):
            raise ValueError("Kayit icerigi sozluk olmali")
        if source_refs is None:
            source_refs = []
        if not isinstance(source_refs, list):
            raise ValueError("Kaynaklar liste olmali")

        record = {
            "id": str(uuid4()),
            "schema_version": self.SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "provider": provider.strip(),
            "status": status,
            "source_refs": source_refs,
            "payload": payload,
        }

        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """INSERT INTO experiences
                    (id, schema_version, created_at, kind, provider, status, source_refs, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record["id"], record["schema_version"], record["created_at"],
                        record["kind"], record["provider"], record["status"],
                        json.dumps(record["source_refs"], ensure_ascii=False),
                        json.dumps(record["payload"], ensure_ascii=False),
                    ),
                )
        return record

    def get(self, record_id):
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT id, schema_version, created_at, kind, provider, status,
                source_refs, payload FROM experiences WHERE id = ?""",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "schema_version": row[1],
            "created_at": row[2],
            "kind": row[3],
            "provider": row[4],
            "status": row[5],
            "source_refs": json.loads(row[6]),
            "payload": json.loads(row[7]),
        }
