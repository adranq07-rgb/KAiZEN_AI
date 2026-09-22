"""Kaizen'in kendi site bilgi deposu: toplanan sayfalar + tam metin arama (SQLite FTS5).

Hermes kapalı olsa bile bu depo çalışır. Sayfalar kaynak adı, adres, tarih ve
içerik özetiyle saklanır; her cevap bu kayıtlara bağlanabilir.
"""
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

from core.text_tr import fold_tr, tokens_tr

STOP_WORDS = {
    "bir", "bu", "ve", "veya", "ile", "icin", "nasil", "nedir", "olan", "olarak", "gore",
    "hangi", "kac", "midir", "mi", "mu", "de", "da", "ne", "kadar", "var", "yok", "en", "cok",
    "hakkinda", "ilgili", "nin", "nun", "in", "un", "yil", "yili", "yilinda",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def effective_year_of(title, content):
    """Sayfanın hangi yıla ait olduğunu tahmin eder (başlıktaki yıl > sık geçen yıl)."""
    current = date.today().year
    lo = current - 10
    in_title = [int(y) for y in re.findall(r"\b(20\d{2})\b", title or "") if lo <= int(y) <= current + 1]
    if in_title:
        return max(in_title)
    counts = {}
    for y in re.findall(r"\b(20\d{2})\b", (content or "")[:20000]):
        y = int(y)
        if lo <= y <= current + 1:
            counts[y] = counts.get(y, 0) + 1
    frequent = [y for y, n in counts.items() if n >= 2]
    pool = frequent or list(counts)
    return max(pool) if pool else None


def best_passages(content, question, max_chars=900, limit=3):
    """İçerikten soruyla en çok örtüşen paragrafları seçer."""
    terms = {t for t in tokens_tr(question) if t not in STOP_WORDS and len(t) > 2}
    if not terms:
        return [content[:max_chars]]
    blocks = [b.strip() for b in re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ0-9])", content) if b.strip()]
    windows = []
    for i, block in enumerate(blocks):
        text = block
        j = i + 1
        while len(text) < max_chars // 2 and j < len(blocks):
            text += " " + blocks[j]
            j += 1
        windows.append(text[:max_chars])
    scored = []
    for text in windows:
        folded = set(tokens_tr(text))
        hits = sum(1 for t in terms if t in folded or any(w.startswith(t[:6]) for w in folded if len(t) >= 6))
        if hits:
            scored.append((hits, -len(text), text))
    scored.sort(reverse=True)
    picked, seen = [], set()
    for _, _, text in scored:
        key = text[:80]
        if key in seen:
            continue
        seen.add(key)
        picked.append(text)
        if len(picked) >= limit:
            break
    return picked or [content[:max_chars]]


class SiteStore:
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
        with closing(self._connect()) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS site_pages (
                    url TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT 'html',
                    published_at TEXT,
                    effective_year INTEGER,
                    fetched_at TEXT NOT NULL,
                    etag TEXT,
                    last_modified TEXT,
                    link_only INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'ok',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_site_pages_source ON site_pages(source_name)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_site_pages_year ON site_pages(effective_year)")
            db.execute("""
                CREATE TABLE IF NOT EXISTS crawl_state (
                    source_name TEXT NOT NULL, key TEXT NOT NULL, value TEXT,
                    PRIMARY KEY (source_name, key)
                )
            """)
            db.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS site_pages_fts
                USING fts5(url UNINDEXED, title, body, tokenize='unicode61')
            """)
            db.commit()
        self._migrate_legacy()

    def _migrate_legacy(self):
        """Eski `documents` tablosundaki kaynak sayfalarını yeni depoya bir kez kopyalar."""
        with closing(self._connect()) as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "documents" not in tables:
                return
            done = db.execute(
                "SELECT value FROM crawl_state WHERE source_name='*' AND key='legacy_migrated'"
            ).fetchone()
            if done:
                return
            rows = db.execute("SELECT * FROM documents").fetchall()
            for row in rows:
                meta = json.loads(row["metadata_json"] or "{}")
                if meta.get("record_type") != "source_page" or not row["url"]:
                    continue
                self._upsert(
                    db, url=row["url"], source_name=row["source_name"], title=row["question"],
                    content=row["content"] or "", kind="html", published_at=row["published_at"],
                    effective_year=row["effective_year"] if "effective_year" in row.keys() else None,
                    link_only=bool(meta.get("link_only")) or not row["content"],
                    metadata={"migrated_from": "documents"},
                )
            db.execute("INSERT OR REPLACE INTO crawl_state VALUES ('*','legacy_migrated','1')")
            db.commit()

    # --- yazma ------------------------------------------------------------------

    def _upsert(self, db, *, url, source_name, title="", content="", kind="html",
                published_at=None, effective_year=None, etag=None, last_modified=None,
                link_only=False, status="ok", metadata=None):
        content_hash = hashlib.sha256(" ".join(content.split()).encode("utf-8")).hexdigest()
        existing = db.execute("SELECT content_hash, status FROM site_pages WHERE url=?", (url,)).fetchone()
        if existing and existing["content_hash"] == content_hash and existing["status"] == status:
            db.execute(
                "UPDATE site_pages SET fetched_at=?, etag=COALESCE(?,etag), last_modified=COALESCE(?,last_modified) WHERE url=?",
                (_now(), etag, last_modified, url),
            )
            return "unchanged"
        if effective_year is None and content:
            effective_year = effective_year_of(title, content)
        db.execute("""
            INSERT INTO site_pages (url, source_name, title, content, content_hash, kind, published_at,
                effective_year, fetched_at, etag, last_modified, link_only, status, metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(url) DO UPDATE SET source_name=excluded.source_name, title=excluded.title,
                content=excluded.content, content_hash=excluded.content_hash, kind=excluded.kind,
                published_at=excluded.published_at, effective_year=excluded.effective_year,
                fetched_at=excluded.fetched_at, etag=excluded.etag, last_modified=excluded.last_modified,
                link_only=excluded.link_only, status=excluded.status, metadata_json=excluded.metadata_json
        """, (url, source_name, title, content, content_hash, kind, published_at, effective_year,
              _now(), etag, last_modified, int(link_only), status, json.dumps(metadata or {}, ensure_ascii=False)))
        db.execute("DELETE FROM site_pages_fts WHERE url=?", (url,))
        if content and status == "ok":
            db.execute("INSERT INTO site_pages_fts (url, title, body) VALUES (?,?,?)",
                       (url, fold_tr(title), fold_tr(content)))
        return "updated" if existing else "new"

    def upsert_page(self, **fields):
        with closing(self._connect()) as db:
            result = self._upsert(db, **fields)
            db.commit()
        return result

    def set_state(self, source_name, key, value):
        with closing(self._connect()) as db:
            db.execute("INSERT OR REPLACE INTO crawl_state VALUES (?,?,?)", (source_name, key, str(value)))
            db.commit()

    def get_state(self, source_name, key, default=None):
        with closing(self._connect()) as db:
            row = db.execute("SELECT value FROM crawl_state WHERE source_name=? AND key=?",
                             (source_name, key)).fetchone()
        return row["value"] if row else default

    # --- okuma ------------------------------------------------------------------

    def get_page(self, url):
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM site_pages WHERE url=?", (url,)).fetchone()
        return dict(row) if row else None

    def known_urls(self, source_name):
        with closing(self._connect()) as db:
            rows = db.execute("SELECT url, fetched_at, etag, last_modified, status FROM site_pages WHERE source_name=?",
                              (source_name,)).fetchall()
        return {r["url"]: dict(r) for r in rows}

    def count(self, source_name=None, with_content=False):
        sql, params = "SELECT COUNT(*) FROM site_pages WHERE 1=1", []
        if source_name:
            sql += " AND source_name=?"
            params.append(source_name)
        if with_content:
            sql += " AND content<>'' AND status='ok'"
        with closing(self._connect()) as db:
            return db.execute(sql, params).fetchone()[0]

    def stats(self):
        with closing(self._connect()) as db:
            rows = db.execute("""
                SELECT source_name, COUNT(*) AS pages,
                       SUM(CASE WHEN content<>'' AND status='ok' THEN 1 ELSE 0 END) AS with_content,
                       MAX(effective_year) AS latest_year, MAX(fetched_at) AS last_fetch
                FROM site_pages GROUP BY source_name ORDER BY source_name
            """).fetchall()
        return [dict(r) for r in rows]

    def iter_pages(self, source_name=None, min_year=None):
        sql, params = "SELECT * FROM site_pages WHERE content<>'' AND status='ok'", []
        if source_name:
            sql += " AND source_name=?"
            params.append(source_name)
        if min_year:
            sql += " AND (effective_year IS NULL OR effective_year>=?)"
            params.append(min_year)
        with closing(self._connect()) as db:
            for row in db.execute(sql, params):
                yield dict(row)

    @staticmethod
    def _fts_query(question, mode="and"):
        terms = [t for t in tokens_tr(question) if t not in STOP_WORDS and len(t) > 1]
        if not terms:
            return None
        parts = []
        for t in terms[:12]:
            stem = t[:6] if len(t) >= 6 else t
            parts.append(f'"{stem}"*' if len(t) >= 4 else f'"{t}"')
        return (" AND " if mode == "and" else " OR ").join(parts)

    def search(self, question, limit=6, prefer_recent=True, min_year=None, source_name=None):
        """Soruyla en iyi eşleşen sayfaları döndürür (önce hepsini içerenler, sonra herhangi biri)."""
        rows, seen = [], set()
        with closing(self._connect()) as db:
            for mode in ("and", "or"):
                query = self._fts_query(question, mode)
                if not query:
                    break
                try:
                    found = db.execute(
                        "SELECT url, bm25(site_pages_fts, 0, 6.0, 1.0) AS rank FROM site_pages_fts "
                        "WHERE site_pages_fts MATCH ? ORDER BY rank LIMIT 60", (query,)
                    ).fetchall()
                except sqlite3.OperationalError:
                    found = []
                for r in found:
                    if r["url"] not in seen:
                        seen.add(r["url"])
                        rows.append((r["url"], r["rank"], mode))
                if len(rows) >= limit:
                    break
            results = []
            current = date.today().year
            for url, rank, mode in rows:
                page = db.execute("SELECT * FROM site_pages WHERE url=?", (url,)).fetchone()
                if not page or page["status"] != "ok":
                    continue
                if source_name and page["source_name"] != source_name:
                    continue
                year = page["effective_year"]
                if min_year and year and year < min_year:
                    continue
                score = -rank + (2.0 if mode == "and" else 0.0)
                if prefer_recent and year:
                    score += max(0, 3 - (current - year)) * 1.0
                item = dict(page)
                item["score"] = score
                item["match"] = mode
                results.append(item)
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]
