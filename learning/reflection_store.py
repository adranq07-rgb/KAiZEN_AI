"""KAIZEN — BÜYÜK GELİŞTİRME PAKETİ #1, Faz D (madde 15, D1-D4): ReflectionStore.

`learning/experience_model.py::Experience`in fiziksel deposu. `memory/principle_registry.py`
ile AYNI ruhta (kendi .sqlite3 dosyası, `_connect()`/`closing()` deseni) ama TAMAMEN ayrı bir
tablo/dosyadır -- principle'lar ZAMANSIZ küratörlü ilkeler, buradaki kayıtlar ise HER
CEVAPLAMA denemesinin (başarılı ya da başarısız) gözlemlenen izidir.

D3 (KESİNLİKLE, birebir): "a new experience never automatically becomes trusted knowledge."
Bu depoda `reusable` alanına giden TEK yol: önce `mark_user_approved(id)` (insanın açık
onayı), SONRA `mark_reusable(id)` -- ikisi de AYRI, açık çağrılardır; `record()` bir kaydı
asla `reusable=True` ile OLUŞTURAMAZ (Experience.__post_init__ zaten bunu reddeder).

D4 (GÜNCEL DURUM -- Learning Loop fazı): depo artık gerçek cevap yaşam döngüsüne bağlıdır,
AMA yalnızca `learning/reflection_lifecycle.py::ReflectionLifecycle` cephesi üzerinden --
`KaizenBrain` bu modülü DOĞRUDAN import etmez. Yeni strateji meta-verisi (research sinyalleri,
güven, provenance, geri bildirim sayaçları) `Experience`'ın 10 alanlık D1/D2 kontratına
DOKUNMADAN ayrı `reflection_meta` tablosunda tutulur (bkz. learning/experience_meta.py)."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from learning.experience_meta import ExperienceMeta
from learning.experience_model import (
    Experience, ExperienceModelError, OUTCOME_FAILURE, OUTCOME_SUCCESS, OUTCOME_UNKNOWN,
    VERIFICATION_NONE, VERIFICATION_USER_APPROVED,
)


class ReflectionStore:
    def __init__(self, db_path=None):
        root = Path(__file__).resolve().parent.parent
        self.db_path = Path(db_path or root / "data" / "kaizen_reflections.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with closing(self._connect()) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS reflections (
                    id TEXT PRIMARY KEY,
                    problem_signature TEXT NOT NULL,
                    selected_principle TEXT,
                    strategy TEXT NOT NULL,
                    tools_used TEXT NOT NULL,
                    evidence_used TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    verification TEXT NOT NULL,
                    user_approved INTEGER NOT NULL,
                    reusable INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS reflection_meta (
                    id TEXT PRIMARY KEY,
                    question_key TEXT NOT NULL,
                    route TEXT NOT NULL,
                    question_kind TEXT NOT NULL,
                    strategy_kind TEXT NOT NULL,
                    research_used INTEGER NOT NULL,
                    research_status TEXT NOT NULL,
                    consensus_status TEXT NOT NULL,
                    official_source_found INTEGER NOT NULL,
                    independent_evidence_count INTEGER NOT NULL,
                    temporal_match TEXT,
                    conflict_count INTEGER NOT NULL,
                    provider_health TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    positive_count INTEGER NOT NULL,
                    negative_count INTEGER NOT NULL,
                    problem_type TEXT,
                    concept_ids TEXT,
                    principle_ids TEXT,
                    recommended_strategy TEXT,
                    current_fact_needed INTEGER
                )
            """)
            # Migration: mevcut DB'ler için eksik kolonları güvenli şekilde ekle.
            # CREATE TABLE IF NOT EXISTS yalnız yeni tabloyu yazar; eski DB'de kolon
            # yoksa INSERT/SELECT "no such column" hatası verir. PRAGMA ile varlık
            # kontrolü yapıp sadece eksik olanları ALTER TABLE ile ekliyoruz.
            columns = {row[1] for row in connection.execute("PRAGMA table_info(reflection_meta)")}
            migrations = {
                "problem_type": "ALTER TABLE reflection_meta ADD COLUMN problem_type TEXT",
                "concept_ids": "ALTER TABLE reflection_meta ADD COLUMN concept_ids TEXT",
                "principle_ids": "ALTER TABLE reflection_meta ADD COLUMN principle_ids TEXT",
                "recommended_strategy": "ALTER TABLE reflection_meta ADD COLUMN recommended_strategy TEXT",
                "current_fact_needed": "ALTER TABLE reflection_meta ADD COLUMN current_fact_needed INTEGER",
            }
            for col, ddl in migrations.items():
                if col not in columns:
                    connection.execute(ddl)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_reflection_meta_key ON reflection_meta(question_key)"
            )
            connection.commit()

    def get_reasoning_meta(self, record_id):
        """ReflectionStore içinden reasoning context metadata'sını oku.
        Sadece YAPI/META alanlarını döndürür; ham cevap/FACT taşımaz."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT problem_type, concept_ids, principle_ids, recommended_strategy,"
                " current_fact_needed FROM reflection_meta WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "problem_type": row["problem_type"],
            "concept_ids": json.loads(row["concept_ids"]) if row["concept_ids"] else [],
            "principle_ids": json.loads(row["principle_ids"]) if row["principle_ids"] else [],
            "recommended_strategy": row["recommended_strategy"],
            "current_fact_needed": bool(row["current_fact_needed"]),
        }

    @staticmethod
    def _row_to_meta(row):
        temporal = row["temporal_match"]
        return ExperienceMeta(
            question_key=row["question_key"], route=row["route"],
            question_kind=row["question_kind"], strategy_kind=row["strategy_kind"],
            research_used=bool(row["research_used"]), research_status=row["research_status"],
            consensus_status=row["consensus_status"],
            official_source_found=bool(row["official_source_found"]),
            independent_evidence_count=row["independent_evidence_count"],
            temporal_match=None if temporal is None else temporal == "1",
            conflict_count=row["conflict_count"], provider_health=row["provider_health"],
            confidence=row["confidence"], provenance=row["provenance"],
            positive_count=row["positive_count"], negative_count=row["negative_count"],
        )

    @staticmethod
    def _row_to_experience(row):
        return Experience(
            problem_signature=row["problem_signature"],
            selected_principle=row["selected_principle"],
            strategy=row["strategy"],
            tools_used=tuple(json.loads(row["tools_used"])),
            evidence_used=tuple(json.loads(row["evidence_used"])),
            outcome=row["outcome"],
            verification=row["verification"],
            user_approved=bool(row["user_approved"]),
            reusable=bool(row["reusable"]),
            created_at=row["created_at"],
        )

    def record(self, experience: Experience, meta: ExperienceMeta = None, reasoning_context=None):
        """Bir `Experience`i kaydeder, kaydın id'sini döner. `experience` zaten
        `Experience.__post_init__` doğrulamasından geçmiştir (D2/D3 orada zorlanır).
        reasoning_context (AccountingReasoningContext): Accountant Reasoning Core v1'den
        gelen internal structured decision state. Yalnızca yapısal alanlar persist edilir."""
        if not isinstance(experience, Experience):
            raise ExperienceModelError("record() yalnizca Experience nesnesi kabul eder")
        record_id = str(uuid4())
        with closing(self._connect()) as connection:
            connection.execute("""
                INSERT INTO reflections (
                    id, problem_signature, selected_principle, strategy, tools_used,
                    evidence_used, outcome, verification, user_approved, reusable, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id, experience.problem_signature, experience.selected_principle,
                experience.strategy, json.dumps(experience.tools_used, ensure_ascii=False),
                json.dumps(experience.evidence_used, ensure_ascii=False),
                experience.outcome, experience.verification,
                int(experience.user_approved), int(experience.reusable),
                experience.created_at,
            ))
            if meta is not None:
                if not isinstance(meta, ExperienceMeta):
                    raise ExperienceModelError("meta yalnizca ExperienceMeta olabilir")
                temporal = None if meta.temporal_match is None else ("1" if meta.temporal_match else "0")
                # Reasoning context persistence (Accountant Reasoning Core v1)
                problem_type = ""
                concept_ids = ""
                principle_ids = ""
                recommended_strategy = ""
                current_fact_needed = None
                if reasoning_context is not None:
                    problem_type = reasoning_context.problem_type or ""
                    concept_ids = json.dumps(list(reasoning_context.relevant_concepts or ()))
                    principle_ids = json.dumps(list(reasoning_context.relevant_principle_ids or ()))
                    recommended_strategy = reasoning_context.recommended_strategy or ""
                    current_fact_needed = (None if reasoning_context.current_fact_needed is None
                                          else int(reasoning_context.current_fact_needed))
                connection.execute("""
                    INSERT INTO reflection_meta (
                        id, question_key, route, question_kind, strategy_kind, research_used,
                        research_status, consensus_status, official_source_found,
                        independent_evidence_count, temporal_match, conflict_count,
                        provider_health, confidence, provenance, positive_count, negative_count,
                        problem_type, concept_ids, principle_ids, recommended_strategy,
                        current_fact_needed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record_id, meta.question_key, meta.route, meta.question_kind,
                    meta.strategy_kind, int(meta.research_used), meta.research_status,
                    meta.consensus_status, int(meta.official_source_found),
                    meta.independent_evidence_count, temporal, meta.conflict_count,
                    meta.provider_health, meta.confidence, meta.provenance,
                    meta.positive_count, meta.negative_count,
                    problem_type, concept_ids, principle_ids, recommended_strategy,
                    current_fact_needed,
                ))
            connection.commit()
        return record_id

    def get(self, record_id):
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM reflections WHERE id = ?", (record_id,)
            ).fetchone()
        return self._row_to_experience(row) if row else None

    def list(self, problem_signature=None, outcome=None, reusable_only=False):
        sql = "SELECT * FROM reflections"
        clauses, params = [], []
        if problem_signature:
            clauses.append("problem_signature = ?")
            params.append(problem_signature)
        if outcome:
            clauses.append("outcome = ?")
            params.append(outcome)
        if reusable_only:
            clauses.append("reusable = 1")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at"
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_experience(r) for r in rows]

    # --- D3: guvene giden TEK yol -- iki AYRI, acik cagri -------------------------------
    def mark_user_approved(self, record_id):
        """İnsanın (mali müşavirin) bu kaydı elle onayladığını işaretler. TEK BAŞINA
        `reusable`'ı DEĞİŞTİRMEZ -- yalnızca onun ön koşulunu sağlar (bkz. mark_reusable)."""
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE reflections SET user_approved = 1 WHERE id = ?", (record_id,)
            )
            connection.commit()
        return cursor.rowcount > 0

    def mark_reusable(self, record_id):
        """Yalnızca `user_approved` ZATEN True ise `reusable`'ı True yapar (D3: otomatik
        güven yok). Onay yoksa `ExperienceModelError` fırlatır -- sessizce yok saymaz."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT user_approved FROM reflections WHERE id = ?", (record_id,)
            ).fetchone()
            if row is None:
                raise ExperienceModelError(f"kayit bulunamadi: {record_id!r}")
            if not row["user_approved"]:
                raise ExperienceModelError(
                    "reusable=True icin once mark_user_approved() cagrilmali (D3: otomatik guven yok)"
                )
            connection.execute(
                "UPDATE reflections SET reusable = 1 WHERE id = ?", (record_id,)
            )
            connection.commit()
        return True

    # --- Learning Loop: meta-veri, geri bildirim, strateji sorgusu -----------------------
    def get_meta(self, record_id):
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM reflection_meta WHERE id = ?", (record_id,)
            ).fetchone()
        return self._row_to_meta(row) if row else None

    def find_latest_by_question_key(self, question_key):
        """Aynı soru (özet anahtarı) için, varsa EN SON STRATEJİ taşıyan kaydın (yoksa en son
        kaydın) id'si -- yanıtı üreten stratejiye geri bildirim gitsin diye. onayla:/düzelt: geri
        bildirimi YALNIZ bu tek kayda uygulanır (tüm sistemi toplu etkileyemez)."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT m.id FROM reflection_meta m JOIN reflections r ON r.id = m.id
                   WHERE m.question_key = ?
                   ORDER BY (m.strategy_kind != '') DESC, r.created_at DESC, r.rowid DESC LIMIT 1""",
                (question_key,),
            ).fetchone()
        return row["id"] if row else None

    def list_with_meta(self, problem_signature=None):
        """Bir problem imzasına ait (id, Experience, ExperienceMeta) üçlüleri.
        problem_signature=None ise TÜM kayıtlar döner."""
        sql = """SELECT r.*, m.question_key, m.route, m.question_kind, m.strategy_kind,
                        m.research_used, m.research_status, m.consensus_status,
                        m.official_source_found, m.independent_evidence_count,
                        m.temporal_match, m.conflict_count, m.provider_health, m.confidence,
                        m.provenance, m.positive_count, m.negative_count
                 FROM reflections r JOIN reflection_meta m ON m.id = r.id"""
        params = []
        if problem_signature is not None:
            sql += " WHERE r.problem_signature = ?"
            params.append(problem_signature)
        sql += " ORDER BY r.created_at"
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [(row["id"], self._row_to_experience(row), self._row_to_meta(row)) for row in rows]

    def list_by_question_kind(self, question_kind):
        """Aynı soru TÜRÜNE (yapısal sınıf) ait (id, Experience, ExperienceMeta) üçlüleri --
        strateji transferi kelimeye değil soru yapısına göre eşleşir."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT r.*, m.question_key, m.route, m.question_kind, m.strategy_kind,
                          m.research_used, m.research_status, m.consensus_status,
                          m.official_source_found, m.independent_evidence_count,
                          m.temporal_match, m.conflict_count, m.provider_health, m.confidence,
                          m.provenance, m.positive_count, m.negative_count
                   FROM reflections r JOIN reflection_meta m ON m.id = r.id
                   WHERE m.question_kind = ? ORDER BY r.created_at""",
                (question_kind,),
            ).fetchall()
        return [(row["id"], self._row_to_experience(row), self._row_to_meta(row)) for row in rows]

    def apply_feedback(self, record_id, positive, allow_reusable=False):
        """Kullanıcı geri bildirimini (onayla:/düzelt:) TEK bir kayda uygular ve etkiyi döner.

        positive=True  : olumlu sayaç +1, `user_approved`=1 (insan onayı). `reusable` YALNIZ
                         çağıran `allow_reusable=True` derse VE kayıtta hiç olumsuz geri
                         bildirim yoksa VE sonuç success ise açılır (D3: iki ayrı adım --
                         önce onay, sonra reusable -- burada da aynı sırayla uygulanır).
        positive=False : olumsuz sayaç +1, sonuç `failure`, onay GERİ ÇEKİLİR ve `reusable`
                         kapatılır. Olumsuz geri bildirim YAPIŞKANDIR: sonradan gelen bir onay
                         `failure`ı `success`e çevirmez ve reusable'ı yeniden açmaz.
        Hiçbir durumda FACT/cevap metni yazılmaz; yalnız sayaç ve bayraklar değişir."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT r.outcome, r.user_approved, r.reusable, m.positive_count, m.negative_count
                   FROM reflections r JOIN reflection_meta m ON m.id = r.id WHERE r.id = ?""",
                (record_id,),
            ).fetchone()
            if row is None:
                return None
            pos, neg = row["positive_count"], row["negative_count"]
            outcome, approved, reusable = row["outcome"], row["user_approved"], row["reusable"]
            verification = None
            if positive:
                pos += 1
                approved = 1
                verification = VERIFICATION_USER_APPROVED
                if neg == 0 and outcome in (OUTCOME_SUCCESS, OUTCOME_UNKNOWN):
                    outcome = OUTCOME_SUCCESS
                    if allow_reusable:
                        reusable = 1
            else:
                neg += 1
                outcome, approved, reusable = OUTCOME_FAILURE, 0, 0
                verification = VERIFICATION_NONE
            connection.execute(
                "UPDATE reflections SET outcome = ?, user_approved = ?, reusable = ?, verification = ? WHERE id = ?",
                (outcome, approved, reusable, verification, record_id),
            )
            connection.execute(
                "UPDATE reflection_meta SET positive_count = ?, negative_count = ?, provenance = ? WHERE id = ?",
                (pos, neg, "user_feedback", record_id),
            )
            connection.commit()
        return {"positive_count": pos, "negative_count": neg, "outcome": outcome,
                "user_approved": bool(approved), "reusable": bool(reusable)}

    def count(self):
        with closing(self._connect()) as connection:
            return connection.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
