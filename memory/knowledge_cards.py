"""Kaizen'in "kendi kendini geliştiren beyni": araştırmadan öğrendiğini kalıcı hafızaya işler.

Hermes (ya da yarın onun yerini alacak başka bir sağlayıcı — bu modül hangi sağlayıcının
kullanıldığını bilmez, yalnız cevap metnini görür) bir soruyu araştırıp cevapladığında,
bu modül cevabı bir "bilgi kartı" olarak saklar:

  - İlk öğrenildiğinde kart "beklemede" (pending) sayılır; bir dahaki sefere aynı/benzer soru
    sorulduğunda Kaizen artık araştırma zincirine gitmeden bu karttan (uyarı notuyla) cevap verir.
  - Kart, mali müşavirin (`onayla:` komutu) veya iki bağımsız araştırma turunun aynı içeriğe
    ulaşmasıyla "doğrulanmış" (confirmed) olur; o zaman `memory/learning_store.py` içine
    (source_type="learned") kalıcı olarak yazılır ve bir sonraki soruda normal ders notu gibi
    kullanılır — araştırma zincirine bir daha ihtiyaç duyulmaz.

Süzgeç mantığı burada da geçerlidir: tek turluk bilgi asla sessizce "kesin bilgi" gibi sunulmaz.
"""
import hashlib
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from core.text_tr import fold_tr

_STOP = {
    "bir", "bu", "ve", "veya", "ile", "icin", "nasil", "nedir", "olan", "olarak", "gore", "hangi",
    "yapilir", "kullanilir", "olur", "edilir", "gerekir", "midir", "mi", "mu", "ne", "kadar", "kac",
    "de", "da", "muhasebe",
}


def _terms(text):
    """Kaba kök çıkarımı: Türkçe ek farklarını (hesaplanır/hesaplama gibi) tolere etmek için
    5 karakterden uzun kelimeler ilk 5 karaktere indirgenir. Bu, yalnız kart eşleştirmede
    (kaba benzerlik) kullanılır; Retriever'ın kesin alıntı süzgeci ayrı ve daha sıkıdır."""
    words = re.findall(r"[a-z0-9]+", fold_tr(text))
    return {w[:5] if len(w) > 5 else w for w in words if w not in _STOP}


def _overlap(a, b):
    """İki metnin anlamlı kelime kümesi ne kadar örtüşüyor (0..1, Jaccard benzerliği)."""
    ta, tb = _terms(a), _terms(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class KnowledgeCardStore:
    """Araştırmadan öğrenilen bilgi kartları: soru, cevap, konu, güven durumu."""

    def __init__(self, db_path=None):
        root = Path(__file__).resolve().parent.parent
        self.db_path = Path(db_path or root / "data" / "kaizen_learning.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS knowledge_cards (
                id TEXT PRIMARY KEY, question TEXT NOT NULL, question_fold TEXT NOT NULL,
                domain TEXT NOT NULL, topic TEXT, answer TEXT NOT NULL, source_label TEXT NOT NULL,
                status TEXT NOT NULL, hit_count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS knowledge_card_contradictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT NOT NULL, detail TEXT NOT NULL,
                created_at TEXT NOT NULL)""")
            db.commit()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _card_id(question):
        return hashlib.sha256(fold_tr(question).encode("utf-8")).hexdigest()[:24]

    # --- yazma ------------------------------------------------------------------
    def remember(self, question, domain, answer, source_label, topic=None, block_confirm=False):
        """Araştırmadan gelen bir cevabı kart olarak kaydeder/günceller.

        Aynı soru (birebir aynı şekilde sorulmuş) daha önce öğrenilmişse, yeni cevap içerik
        olarak örtüşüyorsa (>=0.5) VE bu turun kaynağı ÖNCEKİNDEN FARKLIYSA (`source_label`),
        bu gerçekten bağımsız bir ikinci doğrulama sayılır; ancak o zaman kart kendiliğinden
        'doğrulanmış'a yükselir. Örtüşmüyorsa (mevzuat değişmiş olabilir) yeni bilgi öne alınır
        ve kart tekrar 'beklemede' sayılır. Kesin (elle) onay için `confirm()` (insan onayı
        kaynak/çelişki kontrolünden bağımsız olarak her zaman geçerlidir).

        DÜZELTME (2026-09-23), iki ayrı sorun için:
        1. Eskiden `source_label` HİÇ kontrol edilmiyordu -- Kaizen şu an TEK bir araştırma
           sağlayıcısı (Hermes) kullandığından, aynı sağlayıcının aynı soruyu iki kez benzer
           şekilde cevaplaması ("kendi kendini tekrarlaması") yanlışlıkla "iki bağımsız kaynak
           aynı şeyi söyledi" sayılıp kartı otomatik doğruluyordu. "Tekrar etmek, doğrulanmak
           değildir" -- artık iki turun `source_label`'ı FARKLI olmadıkça otomatik doğrulama
           olmaz (Kaizen tek sağlayıcılıyken bu, doğal olarak yalnız `confirm()` ile -mali
           müşavir onayı- doğrulanabileceği anlamına gelir; ikinci bağımsız bir sağlayıcı
           eklenince bu yol da gerçek anlamda çalışmaya başlar).
        2. `block_confirm=True` (çağıran, bu turun cevabını doğrulanmış parametre defteriyle
           çapraz kontrol edip bir çelişki bulduysa geçer) VEYA bu kart için daha önce
           kapatılmamış bir çelişki kaydı VARSA, bu turda kart 'doğrulanmış'a YÜKSELTİLMEZ --
           bir çelişki kaydının varlığı, tek başına, kartın sessizce onaylanmasını engellemeliydi
           (eskiden engellemiyordu).
        """
        now = datetime.now(timezone.utc).isoformat()
        card_id = self._card_id(question)
        with closing(self._connect()) as db:
            existing = db.execute("SELECT * FROM knowledge_cards WHERE id=?", (card_id,)).fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO knowledge_cards (id, question, question_fold, domain, topic, answer, "
                    "source_label, status, hit_count, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (card_id, question.strip(), fold_tr(question), domain, topic, answer.strip(),
                     source_label, "pending", 1, now, now),
                )
                db.commit()
                return "pending", 1
            similar = _overlap(existing["answer"], answer) >= 0.5
            status = existing["status"]
            hit_count = existing["hit_count"] + 1
            if similar:
                independent_source = source_label != existing["source_label"]
                has_open_contradiction = block_confirm or db.execute(
                    "SELECT 1 FROM knowledge_card_contradictions WHERE card_id=? LIMIT 1", (card_id,)
                ).fetchone() is not None
                if status == "pending" and hit_count >= 2 and independent_source and not has_open_contradiction:
                    status = "confirmed"
            else:
                status, hit_count = "pending", 1
            db.execute(
                "UPDATE knowledge_cards SET answer=?, source_label=?, status=?, hit_count=?, "
                "updated_at=?, topic=COALESCE(?, topic) WHERE id=?",
                (answer.strip(), source_label, status, hit_count, now, topic, card_id),
            )
            db.commit()
            return status, hit_count

    def confirm(self, question):
        """Mali müşavirin (`onayla:` komutu) bir bekleyen kartı elle onaylaması."""
        card = self.recall(question)
        if card is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            db.execute("UPDATE knowledge_cards SET status='confirmed', updated_at=? WHERE id=?",
                       (now, card["id"]))
            db.commit()
        card["status"] = "confirmed"
        return card

    def flag_contradiction(self, card_id, detail):
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            db.execute("INSERT INTO knowledge_card_contradictions (card_id, detail, created_at) VALUES (?,?,?)",
                       (card_id, detail, now))
            db.commit()

    # --- okuma ------------------------------------------------------------------
    def recall(self, question, min_overlap=0.6):
        """Birebir aynı soru veya anlamca çok yakın (kelime örtüşmesi) bir kart varsa döner."""
        card_id = self._card_id(question)
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM knowledge_cards WHERE id=?", (card_id,)).fetchone()
            if row:
                return dict(row)
            best, best_score = None, 0.0
            for candidate in db.execute("SELECT * FROM knowledge_cards"):
                score = _overlap(candidate["question"], question)
                if score > best_score:
                    best, best_score = candidate, score
            if best is not None and best_score >= min_overlap:
                return dict(best)
        return None

    def all_cards(self, status=None):
        sql, params = "SELECT * FROM knowledge_cards", []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC"
        with closing(self._connect()) as db:
            return [dict(r) for r in db.execute(sql, params)]

    def stats(self):
        with closing(self._connect()) as db:
            rows = db.execute("SELECT status, COUNT(*) c FROM knowledge_cards GROUP BY status").fetchall()
            contradictions = db.execute("SELECT COUNT(*) FROM knowledge_card_contradictions").fetchone()[0]
        counts = {r["status"]: r["c"] for r in rows}
        counts["contradictions"] = contradictions
        return counts

    def contradictions(self):
        with closing(self._connect()) as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM knowledge_card_contradictions ORDER BY created_at DESC")]
