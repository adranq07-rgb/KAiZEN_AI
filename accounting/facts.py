"""Süzgeç: sitelerden yıllık parametreleri (had, oran, tavan) çıkarır, uzlaştırır ve yıllara göre saklar.

Akış:  site sayfaları  ->  cümle bazlı aday çıkarımı  ->  yıl+konu bazında uzlaşı  ->  `facts` tablosu.
Kural (kullanıcının süzgeç kuralı): aynı değer birbirinden bağımsız en az iki kaynakta görülürse
veya resmî kaynakta geçerse doğrulanır. Kanun değişip yeni değer başka kaynaklarda da görülürse
yeni değer doğrulanır ve eski değer geçmişe yazılır. Cevap her zaman en güncel yıldan verilir.
"""
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from accounting.consensus import AccountingConsensus, FactCandidate
from accounting.source_registry import trusted_source_for_url
from core.text_tr import fold_tr, format_number_tr, parse_tr_number

TOPICS_PATH = Path(__file__).resolve().parent.parent / "config" / "fact_topics.json"

_TR_MAP = str.maketrans({"ı": "i", "İ": "i", "I": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
                         "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})


def fold_keep_len(text):
    """Konumları bozmayan normalleştirme (uzunluk aynı kalır)."""
    return text.translate(_TR_MAP).lower()


@dataclass(frozen=True)
class FactTopic:
    id: str
    title: str
    unit: str
    anchors: tuple
    require: tuple = ()
    require_any: tuple = ()
    avoid: tuple = ()
    question_terms: tuple = ()


def load_topics(path=None):
    data = json.loads(Path(path or TOPICS_PATH).read_text(encoding="utf-8"))
    topics = []
    for raw in data["topics"]:
        topics.append(FactTopic(
            id=raw["id"], title=raw["title"], unit=raw["unit"],
            anchors=tuple(fold_tr(a) for a in raw["anchors"]),
            require=tuple(fold_tr(a) for a in raw.get("require", [])),
            require_any=tuple(fold_tr(a) for a in raw.get("require_any", [])),
            avoid=tuple(fold_tr(a) for a in raw.get("avoid", [])),
            question_terms=tuple(fold_tr(a) for a in raw.get("question_terms", [])),
        ))
    return topics


_PERCENT = re.compile(r"(?:%\s*(\d{1,3}(?:[.,]\d+)?)|(\d{1,3}(?:[.,]\d+)?)\s*%|y[uü]zde\s+(\d{1,3}(?:[.,]\d+)?))", re.I)
# (?<!\d)(?<!\d\s): boşlukla binlik ayrılmış sayıların (ör. "4 000 000 TL") son parçasını
# ("000 TL" gibi) yanlışlıkla tek başına yakalamayı önler -- öyle bir sayı hiç yakalanmaz,
# yanlış (kırpılmış) değer üretmektense hiç değer üretmemeyi tercih ederiz.
_TL = re.compile(r"(?<!\d)(?<!\d\s)(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)\s*(?:TL|₺|Türk\s+lira|lira)\b", re.I)
_TL_PREFIX = re.compile(r"(?:₺)\s*(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)")
_MILLE = re.compile(r"binde\s*(\d+(?:[.,]\d+)?)", re.I)
_YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def _values(sentence, unit):
    out = []
    if unit == "percent":
        for m in _PERCENT.finditer(sentence):
            raw = next(g for g in m.groups() if g)
            out.append((m.start(), raw, "%" + raw))
    elif unit == "per_mille":
        for m in _MILLE.finditer(sentence):
            out.append((m.start(), m.group(1), "binde " + m.group(1)))
    else:
        for m in list(_TL.finditer(sentence)) + list(_TL_PREFIX.finditer(sentence)):
            out.append((m.start(), m.group(1), m.group(1) + " TL"))
    out.sort()
    return out


def split_sentences(text):
    for block in re.split(r"\n+", text):
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ0-9•\-–])", block):
            sentence = " ".join(sentence.split())
            if 25 <= len(sentence) <= 600:
                yield sentence


class FactExtractor:
    def __init__(self, topics=None, current_year=None):
        self.topics = topics if topics is not None else load_topics()
        self.current_year = current_year or date.today().year

    def _year_for(self, folded, position, default):
        years = [(m.start(), int(m.group(1))) for m in _YEAR.finditer(folded)
                 if self.current_year - 10 <= int(m.group(1)) <= self.current_year + 1]
        if not years:
            return default
        before = [(pos, y) for pos, y in years if pos <= position and position - pos <= 110]
        if before:
            return before[-1][1]
        after = [(pos, y) for pos, y in years if pos > position and pos - position <= 40]
        if after:
            return after[0][1]
        return max(y for _, y in years) if len(years) == 1 else default

    def extract(self, page):
        """Bir site sayfasından FactCandidate listesi çıkarır."""
        content, url = page.get("content") or "", page["url"]
        default_year = page.get("effective_year")
        found = {}
        for sentence in split_sentences(content):
            folded = fold_keep_len(sentence)
            for topic in self.topics:
                anchor_pos = [folded.find(a) for a in topic.anchors if a in folded]
                if not anchor_pos:
                    continue
                if topic.require and not all(r in folded for r in topic.require):
                    continue
                if topic.require_any and not any(r in folded for r in topic.require_any):
                    continue
                if any(a in folded for a in topic.avoid):
                    continue
                values = _values(sentence, topic.unit)
                if not values or len(values) > 4:
                    continue
                anchor = min(anchor_pos)
                for pos, raw, display in values:
                    year = self._year_for(folded, pos, default_year)
                    if not year:
                        continue
                    distance = abs(pos - anchor) + (0 if pos >= anchor else 15)
                    key = (topic.id, year)
                    if key in found and found[key][0] <= distance:
                        continue
                    found[key] = (distance, FactCandidate(topic.id, display, year, url, sentence))
        return [candidate for _, candidate in found.values()]


class FactRegistry:
    def __init__(self, db_path=None, topics=None):
        root = Path(__file__).resolve().parent.parent
        self.db_path = Path(db_path or root / "data" / "accounting_knowledge.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.topics = topics if topics is not None else load_topics()
        self._by_id = {t.id: t for t in self.topics}
        with closing(self._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS facts (
                topic TEXT NOT NULL, year INTEGER NOT NULL, value TEXT, status TEXT NOT NULL,
                sources_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
                first_seen TEXT NOT NULL, last_checked TEXT NOT NULL,
                PRIMARY KEY (topic, year))""")
            db.execute("""CREATE TABLE IF NOT EXISTS fact_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, year INTEGER NOT NULL,
                old_value TEXT, new_value TEXT, old_status TEXT, new_status TEXT, changed_at TEXT NOT NULL)""")
            db.commit()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    # --- yazma ------------------------------------------------------------------
    def record(self, topic, year, status, value, sources, evidence):
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            old = db.execute("SELECT * FROM facts WHERE topic=? AND year=?", (topic, year)).fetchone()
            if old and (old["value"], old["status"]) != (value, status):
                db.execute("INSERT INTO fact_history (topic,year,old_value,new_value,old_status,new_status,changed_at) "
                           "VALUES (?,?,?,?,?,?,?)", (topic, year, old["value"], value, old["status"], status, now))
            db.execute("""INSERT INTO facts (topic,year,value,status,sources_json,evidence_json,first_seen,last_checked)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(topic,year) DO UPDATE SET value=excluded.value, status=excluded.status,
                    sources_json=excluded.sources_json, evidence_json=excluded.evidence_json,
                    last_checked=excluded.last_checked""",
                       (topic, year, value, status, json.dumps(sources, ensure_ascii=False),
                        json.dumps(evidence, ensure_ascii=False), old["first_seen"] if old else now, now))
            db.commit()

    def rebuild(self, store, min_year=None, extractor=None):
        """Depodaki tüm sayfaları tarar; konu ve yıl bazında uzlaşı kurup `facts` tablosunu günceller."""
        extractor = extractor or FactExtractor(self.topics)
        min_year = min_year or (date.today().year - 3)
        grouped = {}
        pages = 0
        for page in store.iter_pages():
            pages += 1
            for candidate in extractor.extract(page):
                if candidate.effective_year < min_year:
                    continue
                grouped.setdefault((candidate.topic, candidate.effective_year), []).append(candidate)
        consensus = AccountingConsensus()
        summary = {"pages": pages, "topics_found": 0, "verified": 0, "pending": 0, "conflict": 0}
        for (topic, year), candidates in sorted(grouped.items()):
            result = consensus.decide(candidates)
            evidence = {c.source_url: c.evidence for c in candidates}
            values = sorted({c.value for c in candidates})
            if result.status == "verified":
                status, value, sources = "verified", result.value, list(result.sources)
            elif result.status == "conflict":
                status, value, sources = "conflict", " / ".join(values), [c.source_url for c in candidates]
            else:
                status, value, sources = "pending", values[0], [c.source_url for c in candidates]
            self.record(topic, year, status, value, sources, {u: evidence[u] for u in sources if u in evidence})
            summary["topics_found"] += 1
            summary[status if status in summary else "pending"] += 1
        return summary

    # --- okuma ------------------------------------------------------------------
    def rows(self, topic=None):
        sql, params = "SELECT * FROM facts", []
        if topic:
            sql += " WHERE topic=?"
            params.append(topic)
        sql += " ORDER BY topic, year DESC"
        with closing(self._connect()) as db:
            return [dict(r) for r in db.execute(sql, params)]

    def history(self, topic):
        with closing(self._connect()) as db:
            return [dict(r) for r in db.execute("SELECT * FROM fact_history WHERE topic=? ORDER BY changed_at", (topic,))]

    def find_topics(self, question):
        """Soruyla en iyi eşleşen konular (eşitlik varsa hepsi: 'asgari ücret' -> brüt ve net)."""
        folded = fold_tr(question)
        scored = []
        for topic in self.topics:
            hits = [t for t in topic.question_terms if t in folded]
            if hits:
                scored.append((max(len(t) for t in hits), topic))
        if not scored:
            return []
        best = max(score for score, _ in scored)
        return [topic for score, topic in scored if score == best]

    def find_topic(self, question):
        found = self.find_topics(question)
        return found[0] if found else None

    def answer(self, question, current_year=None):
        """Yıllık parametre sorusunu, en güncel doğrulanmış değerden ve kaynaklarıyla cevaplar."""
        answers = [a for a in (self._answer_topic(t, question) for t in self.find_topics(question)) if a]
        return "\n\n".join(answers) if answers else None

    def _answer_topic(self, topic, question):
        rows = self.rows(topic.id)
        if not rows:
            return None
        asked = [int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", question)]
        if asked:
            rows = [r for r in rows if r["year"] in asked] or None
            if rows is None:
                return (f"Kaizen: {topic.title} için {', '.join(map(str, asked))} yılına ait kayıt henüz yok; "
                        "site güncellemesinden sonra tekrar sorabilirsiniz.")
        verified = [r for r in rows if r["status"] == "verified"]
        chosen = verified[0] if verified else rows[0]
        newer_unverified = [r for r in rows if r["year"] > chosen["year"] and r["status"] != "verified"]
        sources = json.loads(chosen["sources_json"])
        evidence = json.loads(chosen["evidence_json"])
        lines = []
        if chosen["status"] == "verified":
            lines.append(f"SONUÇ: {topic.title} ({chosen['year']}): {chosen['value']}")
            lines.append(f"DOĞRULAMA: {len(sources)} kaynakta aynı değer bulundu (uzlaşı sağlandı).")
        elif chosen["status"] == "conflict":
            lines.append(f"Kaizen: {topic.title} ({chosen['year']}) için kaynaklar çelişiyor: {chosen['value']}. Kesin cevap veremiyorum.")
        else:
            lines.append(f"Kaizen: {topic.title} ({chosen['year']}) için yalnız tek kaynakta {chosen['value']} görüldü; henüz doğrulanmadı.")
        for note in newer_unverified:
            lines.append(f"NOT: {note['year']} yılı için {note['value']} değeri görüldü ama {'kaynaklar çelişiyor' if note['status'] == 'conflict' else 'henüz ikinci bir kaynakla doğrulanmadı'}.")
        lines.append("KAYNAKLAR: " + " ; ".join(sources[:4]))
        if sources and sources[0] in evidence:
            lines.append("KANIT: " + evidence[sources[0]])
        return "\n".join(lines)
