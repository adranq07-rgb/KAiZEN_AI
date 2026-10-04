"""KAIZEN — Learning Brain v1: Principle Registry (iş emri madde 5).

FACT != PRINCIPLE (iş emri madde 4): bu depo yalnız ZAMANSIZ, küratörlü muhasebe
DÜŞÜNME KURALLARINI tutar (ör. "gelir/gider ait olduğu döneme yazılır"). Yıllık
oran/parasal sınır/tarih/mevzuat hükmü gibi GÜNCEL FACT'ler burada ASLA saklanmaz --
onlar `accounting/facts.py::FactRegistry` + `accounting/consensus.py`'de kalmaya devam
eder (bkz. test_principle_registry_rejects_rows_containing_annual_figures aşağıda,
ve tests/test_learning_transfer.py::test_transfer_dataset_no_annual_figures_leak...).

`accounting/facts.py::FactRegistry`'nin SQLite deseni (kendi .sqlite3 dosyası,
`_connect()`/`_initialize()`, `closing()` context manager) burada da izlenir -- ama
KASITLI olarak yalnız `keyword -> principle` tablosu YAPILMADI (madde 5): her satır
problem_structure/applicability/non_applicability/examples/counter_examples/
source/status alanlarını taşır, insan tarafından denetlenebilir bir provenance
zinciriyle (madde 15: "küratörlü, açık kaynak/provenance sahibi, insan tarafından
kontrol edilebilir").
"""
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

# Yıl gibi görünen 4 haneli sayı (2020-2099) -- bir principle satırına YANLIŞLIKLA güncel
# bir FACT (yıl/oran/tutar) sızmasını STATIK olarak engellemek için (madde 4/16/23).
_YEAR_PATTERN = re.compile(r"\b20[2-9]\d\b")

STATUS_ACTIVE = "active"
STATUS_DRAFT = "draft"
STATUS_QUARANTINED = "quarantined"


class PrincipleRegistryError(ValueError):
    """Bir principle satırı FACT sızıntısı veya eksik alan içerdiğinde (madde 4/16)."""


class PrincipleRegistry:
    @staticmethod
    def accounting_contract(row):
        """Normalize the existing curated principle without a second store/schema."""
        structure = row.get("problem_structure", {})
        return {"principle_id": row["principle_id"], "name": row["name"],
                "scope": row.get("domain", "accounting"),
                "conditions": row.get("applicability", []),
                "accounting_effect": structure.get("accounting_effect", row["description"]),
                "exceptions": row.get("non_applicability", []),
                "required_facts": structure.get("required_facts", ["economic_event"]),
                "source_requirement": row.get("source", ""),
                "confidence": row.get("confidence", "low"),
                "validation_state": row.get("status", STATUS_ACTIVE)}

    def __init__(self, db_path=None):
        root = Path(__file__).resolve().parent.parent
        self.db_path = Path(db_path or root / "data" / "kaizen_principles.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with closing(self._connect()) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS principles (
                    principle_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    problem_structure TEXT NOT NULL,
                    applicability TEXT NOT NULL,
                    non_applicability TEXT NOT NULL,
                    examples TEXT NOT NULL,
                    counter_examples TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    independent_support_count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    confidence TEXT NOT NULL DEFAULT 'low',
                    supporting_experience_ids TEXT NOT NULL DEFAULT '[]',
                    validation_history TEXT NOT NULL DEFAULT '[]',
                    quarantine_reason TEXT
                )
            """)
            connection.commit()

    # --- FACT sızıntısı koruması (madde 4/16, statik/yazma-zamanı kontrol) --------------
    @staticmethod
    def _assert_no_fact_leak(principle_id, name, description):
        for label, value in (("name", name), ("description", description)):
            if _YEAR_PATTERN.search(value):
                raise PrincipleRegistryError(
                    f"principle {principle_id!r}: {label} içinde bir YIL var (FACT sızıntısı, "
                    f"madde 4/16 KESİNLİKLE YASAK): {value!r}"
                )

    def upsert(self, *, principle_id, name, description, domain, problem_structure,
               applicability, non_applicability, examples, counter_examples,
               source, status=STATUS_ACTIVE, independent_support_count=0,
               success_count=0, failure_count=0, confidence="low",
               supporting_experience_ids=(), validation_history=(),
               quarantine_reason=None):
        """Bir ilkeyi ekler/günceller. `problem_structure`/`applicability`/
        `non_applicability`/`examples`/`counter_examples` liste/dict olabilir (JSON'a
        çevrilir). `source`, provenance (madde 15) -- BOŞ OLAMAZ."""
        if not source or not str(source).strip():
            raise PrincipleRegistryError(
                f"principle {principle_id!r}: source/provenance zorunlu (madde 15)"
            )
        self._assert_no_fact_leak(principle_id, name, description)
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            existing = connection.execute(
                "SELECT created_at FROM principles WHERE principle_id = ?", (principle_id,)
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            connection.execute("""
                INSERT INTO principles (
                    principle_id, name, description, domain, problem_structure,
                    applicability, non_applicability, examples, counter_examples,
                    source, status, created_at, updated_at,
                    independent_support_count, success_count, failure_count,
                    confidence, supporting_experience_ids, validation_history,
                    quarantine_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(principle_id) DO UPDATE SET
                    name=excluded.name, description=excluded.description,
                    domain=excluded.domain, problem_structure=excluded.problem_structure,
                    applicability=excluded.applicability,
                    non_applicability=excluded.non_applicability,
                    examples=excluded.examples, counter_examples=excluded.counter_examples,
                    source=excluded.source, status=excluded.status,
                    updated_at=excluded.updated_at,
                    independent_support_count=excluded.independent_support_count,
                    success_count=excluded.success_count,
                    failure_count=excluded.failure_count,
                    confidence=excluded.confidence,
                    supporting_experience_ids=excluded.supporting_experience_ids,
                    validation_history=excluded.validation_history,
                    quarantine_reason=excluded.quarantine_reason
            """, (
                principle_id, name, description, domain,
                json.dumps(problem_structure, ensure_ascii=False),
                json.dumps(applicability, ensure_ascii=False),
                json.dumps(non_applicability, ensure_ascii=False),
                json.dumps(examples, ensure_ascii=False),
                json.dumps(counter_examples, ensure_ascii=False),
                source, status, created_at, now,
                int(independent_support_count), int(success_count), int(failure_count),
                confidence, json.dumps(supporting_experience_ids, ensure_ascii=False),
                json.dumps(validation_history, ensure_ascii=False),
                quarantine_reason,
            ))
            connection.commit()
        return principle_id

    @staticmethod
    def _row_to_dict(row):
        d = dict(row)
        for key in ("problem_structure", "applicability", "non_applicability",
                    "examples", "counter_examples"):
            d[key] = json.loads(d[key])
        d["independent_support_count"] = int(d.get("independent_support_count", 0))
        d["success_count"] = int(d.get("success_count", 0))
        d["failure_count"] = int(d.get("failure_count", 0))
        d["confidence"] = d.get("confidence", "low")
        d["supporting_experience_ids"] = tuple(json.loads(d.get("supporting_experience_ids", "[]")))
        d["validation_history"] = json.loads(d.get("validation_history", "[]"))
        d["quarantine_reason"] = d.get("quarantine_reason")
        return d

    def get(self, principle_id):
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM principles WHERE principle_id = ?", (principle_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def all(self, domain=None, status=None):
        sql = "SELECT * FROM principles"
        clauses, params = [], []
        if domain:
            clauses.append("domain = ?")
            params.append(domain)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY principle_id"
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count(self):
        with closing(self._connect()) as connection:
            return connection.execute("SELECT COUNT(*) FROM principles").fetchone()[0]
