"""Kaizen'in kendi hafızasından kanıt toplama.

İki kaynağa birlikte bakar:
  1) Ders notları / öğretilmiş bilgiler (LearningStore)  -> "ders"
  2) Güvenilir sitelerden toplanan sayfalar (SiteStore)   -> "site"

Yapay zeka modeli kapalıyken de (Hermes yok, yerel model yok) kanıttan
düz bir cevap üretebilir (extractive_answer).
"""
from datetime import date

from accounting.accounting_brain import AccountingBrain
from accounting.site_store import STOP_WORDS, best_passages
from core.text_tr import fold_tr, stem_tr, tokens_tr


# Soru kalıbı sözcükleri: cevabın metinde aynen geçmesi beklenmez
FILLER = {
    "kullanilir", "kullanilmali", "yapilir", "eklenir", "olur", "olusturulur", "yazilir", "nedir", "kac", "kadar",
    "formul", "formulu", "formulunu", "formulleri", "fonksiyon", "fonksiyonu", "islev", "islevi",
    "kullanimi", "ornek", "ornegi", "nelerdir", "anlatir", "misin", "musun",
}


class Evidence:
    """Tek bir kanıt parçası: hangi kaynaktan, hangi yıldan, ne yazıyor."""

    __slots__ = ("kind", "label", "text", "url", "year", "source_name", "score", "curated", "keywords")

    def __init__(self, kind, label, text, url=None, year=None, source_name=None, score=0.0, curated=False, keywords=""):
        self.kind = kind
        self.label = label
        self.text = text
        self.url = url
        self.year = year
        self.source_name = source_name
        self.score = score
        self.curated = curated
        self.keywords = keywords

    def source_line(self):
        if self.kind == "site":
            year = f" ({self.year})" if self.year else ""
            return f"{self.label}{year} — {self.url}"
        return self.label


class Retriever:
    def __init__(self, learning_store, site_store=None, accounting_brain=None):
        self.learning_store = learning_store
        self.site_store = site_store
        self.accounting_brain = accounting_brain or AccountingBrain(learning_store)

    # --- toplama -----------------------------------------------------------------
    def gather(self, question, domain, current=False, course_limit=3, site_limit=3):
        """Soruya en uygun kanıtları getirir.

        current=True (güncel mevzuat/oran sorusu): site sayfaları öne alınır, ders notları destek olur.
        """
        course = self._course_evidence(question, domain, course_limit)
        sites = self._site_evidence(question, site_limit) if domain in ("accounting", "general") else []
        return (sites + course) if current else (course + sites)

    def _course_evidence(self, question, domain, limit):
        if domain == "accounting":
            _, rows = self.accounting_brain.retrieve(question, limit=limit)
        else:
            memory_domain = domain if domain in {"mathematics", "office"} else None
            rows = self.learning_store.search(question, domain=memory_domain, limit=limit)
        seen, unique = set(), []
        for row in rows:
            key = (row["subject"], row.get("section"), " ".join(row["text"].split())[:120])
            if key not in seen:
                seen.add(key)
                unique.append(row)
        rows = unique
        return [
            Evidence(
                "ders",
                f"{row['subject']} — {row.get('section') or row.get('locator') or 'bölüm'}",
                row["text"].split(" Anahtar sözcükler:")[0][:5000],
                curated=row.get("source_type") == "curated",
                keywords=row["text"].partition(" Anahtar sözcükler:")[2],
            )
            for row in rows
        ]

    def _site_evidence(self, question, limit):
        if self.site_store is None:
            return []
        try:
            pages = self.site_store.search(question, limit=limit, prefer_recent=True)
        except Exception:  # bozuk/eksik veritabanı cevabı engellemesin
            return []
        items = []
        for page in pages:
            passages = best_passages(page["content"], question, max_chars=1200, limit=2)
            passages = [t for t in passages if self.coverage(question, t) >= 0.75 and self.phrase_ok(question, t)]
            if not passages:
                continue  # soruyla ilgisiz sayfa kanıt sayılmaz
            items.append(Evidence(
                "site",
                f"{page['source_name']}: {page['title'] or page['url']}",
                "\n".join(passages),
                url=page["url"],
                year=page.get("effective_year"),
                source_name=page["source_name"],
                score=page.get("score", 0.0),
            ))
        return items

    # --- cevap üretimi -------------------------------------------------------------
    @staticmethod
    def build_prompt(question, domain, evidence, today=None):
        today = today or date.today().isoformat()
        blocks = []
        for index, item in enumerate(evidence[:6], start=1):
            year = f" | yıl: {item.year}" if item.year else ""
            blocks.append(f"[{index}] ({item.kind}{year}) {item.label}\n{item.text[:4000]}")
        return f"""Sen Kaizen AI'sın: Türkiye'de çalışan mali müşavir gibi düşünen bir muhasebe ve matematik asistanısın.
Bugün: {today}
Alan: {domain}
Soru: {question}

Kurallar:
- Yalnız aşağıdaki KANITLARA dayan. Soruyu doğrudan ve net cevapla.
- Yıla bağlı bir sınır/oran soruluyorsa kanıtlar arasındaki EN YENİ yılı kullan; yılı belirt.
- Kanıtlar çelişiyorsa bunu açıkça yaz; birini uydurma tercih etme.
- Kanıtta yoksa tam olarak 'Bu bilgi yerel hafızada bulunamadı.' yaz. Tutar, oran, hesap kodu, formül veya madde numarası uydurma.
- Muhasebe sorusunda SONUÇ, MUHASEBE UYGULAMASI ve DAYANAK başlıklarını kullan; kayıt soruluyorsa borç/alacak yönünü ve nedenini yaz.
- Kullandığın kanıtların [numaralarını] DAYANAK bölümünde yaz.

KANITLAR:
{chr(10).join(blocks)}
"""

    @staticmethod
    def sources_block(evidence, limit=5):
        lines = []
        seen = set()
        for item in evidence[:limit]:
            line = item.source_line()
            if line in seen:
                continue
            seen.add(line)
            lines.append(f"- {line}")
        return "KAYNAKLAR:\n" + "\n".join(lines) if lines else ""

    @staticmethod
    def _terms(question):
        seen, terms = set(), []
        for t in tokens_tr(question):
            if t not in STOP_WORDS and t not in FILLER and len(t) > 2 and t not in seen:
                seen.add(t)
                terms.append(t)
        return terms

    @staticmethod
    def _positions(term, words):
        # Gerçek (iki yönlü) Türkçe ek kırpma: 'muhasebede' (soru) ~ 'muhasebe'/'muhasebesi'
        # (metin) gibi durumlarda hangi tarafın ekli olduğu önemli değil; ikisi de aynı köke
        # indirgenip öyle karşılaştırılır (bkz. core.text_tr.stem_tr). Eskiden yalnız tek yönlü
        # bir kırpma vardı (sorudaki kök -> metindeki ekli hal), bu yüzden ek soruda olunca
        # ("muhasebede") eşleşme kaçıyordu.
        term_stem = stem_tr(term)

        def same(word):
            return word == term or stem_tr(word) == term_stem
        return [i for i, w in enumerate(words) if same(w)]

    @staticmethod
    def coverage(question, text):
        """Sorudaki anlamlı kelimelerin kaçının metinde geçtiği (0..1)."""
        terms = Retriever._terms(question)
        if not terms:
            return 0.0
        words = tokens_tr(text)
        return sum(1 for t in terms if Retriever._positions(t, words)) / len(terms)

    @staticmethod
    def phrase_ok(question, text, window=5):
        """Metinde bulunan soru kelimeleri, sorudaki sıraya yakın komşuluklarla birlikte mi geçiyor?

        'kurumlar vergisi oranı' sorusu için 'kurumlar vergisi beyannamesi ... yeniden değerleme oranı'
        gibi kelimeleri uzak yerlerde geçen alakasız bir paragraf reddedilir."""
        terms = Retriever._terms(question)
        words = tokens_tr(text)
        found = [(t, Retriever._positions(t, words)) for t in terms]
        found = [(t, pos) for t, pos in found if pos]
        pairs = list(zip(found, found[1:]))
        if not pairs:
            return len(found) >= 1
        close = sum(1 for (_, a), (_, b) in pairs if any(abs(x - y) <= window for x in a for y in b))
        return close >= -(-len(pairs) * 6 // 10)  # ceil(0.6 * pairs)

    @staticmethod
    def extractive_answer(question, evidence, max_items=2, strict=False):
        """Model yokken: kanıtın soruyla en çok örtüşen bölümünü kaynağıyla birlikte gösterir.

        Soruyla yeterince örtüşen bölüm yoksa None döner (alakasız metni cevap gibi sunmayız)."""
        min_coverage = 1.0 if strict else 0.6  # güncel/parametre sorusunda soru kelimelerinin hepsi geçmeli
        picked = []
        for item in evidence:
            # Elle derlenmiş şablonlar kısa ve bütündür: parçalamadan olduğu gibi göster
            excerpt = (item.text[:900] if item.curated
                       else best_passages(item.text, question, max_chars=700, limit=1)[0]).strip()
            probe = excerpt if strict else f"{item.label} {excerpt} {item.keywords}"
            if (Retriever.coverage(question, probe) >= min_coverage
                    and Retriever.phrase_ok(question, probe, window=5 if strict else 12)):
                picked.append((item, excerpt))
            if len(picked) >= max_items:
                break
        if not picked:
            return None
        parts = ["Kaizen (yerel hafıza, yapay zeka modeli olmadan): En ilgili kayıtlar —"]
        for item, excerpt in picked:
            year = f" ({item.year})" if item.year else ""
            parts.append(f"\n▸ {item.label}{year}\n{excerpt}")
        parts.append("\n" + Retriever.sources_block([i for i, _ in picked], limit=max_items + 2))
        return "\n".join(parts)


def says_not_found(text):
    """Modelin 'kanıtta yok' dediği cevap mı?"""
    folded = fold_tr(text or "")
    return "bulunamadi" in folded and ("yerel hafiza" in folded or "yerel ders" in folded or "kanit" in folded)
