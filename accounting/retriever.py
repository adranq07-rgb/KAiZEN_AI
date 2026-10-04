"""Kaizen'in kendi hafızasından kanıt toplama.

İki kaynağa birlikte bakar:
  1) Ders notları / öğretilmiş bilgiler (LearningStore)  -> "ders"
  2) Güvenilir sitelerden toplanan sayfalar (SiteStore)   -> "site"

Yapay zeka modeli kapalıyken de (Hermes yok, yerel model yok) kanıttan
düz bir cevap üretebilir (extractive_answer).
"""
import math
import time
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


# KÖK NEDEN #2 (33 soruluk sınav analizi): "nasıl hesaplanır", "ne fark eder", "anlaşılır",
# "paylaşılıyor" gibi SORU İSKELETİ sözcükleri kanıt metninde aynen geçmediği için, ilgili
# kayıt VARKEN kapsama (coverage) eşiği (0.6) geçilemiyordu. Eşik DÜŞÜRÜLMEDİ; yalnız soru
# iskeleti olan sözcükler "gerekli terim" sayılmıyor.
_QUESTION_FRAME_WORDS = {"nasil", "neden", "niye", "hangi", "nelerdir", "arasinda", "arasindaki",
                         "aradaki", "hakkinda"}
# 'fark' YALNIZ karşılaştırma iskeleti olarak ('ne fark eder', 'arasındaki fark') iskelettir;
# 'tarih farkı bulma' gibi bir KAVRAM sözcüğü olarak geçtiğinde terim SAYILIR (golden exam kanıtı).
_COMPARE_FRAME_PREVIOUS = {"ne", "arasinda", "arasindaki", "aradaki"}
_HOW_FRAME_VERB_ENDINGS = (
    "anir", "enir", "ilir", "ulur", "inir", "unur", "ilmali", "ulmali", "ilmeli", "iliyor",
    "uluyor", "aniyor", "eniyor", "ilmektedir", "anmaktadir",
)


def _frame_term(term, previous):
    """Soru iskeleti mi? -- 'nasıl X-ılır/X-ılıyor' kalıbındaki edilgen fiil ve genel karşılaştırma
    iskeleti ('ne fark eder', 'arasındaki fark'). İsim/kavram sözcükleri ASLA iskelet sayılmaz."""
    if term in _QUESTION_FRAME_WORDS:
        return True
    if term == "fark" and previous in _COMPARE_FRAME_PREVIOUS:
        return True
    if term == "eder" and previous == "fark":
        return True
    return previous == "nasil" and len(term) >= 7 and term.endswith(_HOW_FRAME_VERB_ENDINGS)


def _match_key(word):
    """Karşılaştırma anahtarı: ek kırpma + Türkçe ünsüz yumuşaması (seçenek ~ seçeneği: k/ğ).
    Yalnız EŞİTLİK karşılaştırmasında kullanılır (iki taraf da aynı işlemden geçer)."""
    stem = stem_tr(word)
    return stem[:-1] + "k" if len(stem) >= 5 and stem.endswith("g") else stem


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
    def __init__(self, learning_store, site_store=None, accounting_brain=None,
                 embedding_client=None, embedding_cache=None, hybrid_enabled=False):
        self.learning_store = learning_store
        self.site_store = site_store
        self.accounting_brain = accounting_brain or AccountingBrain(learning_store)
        # TAM ENTEGRASYON FAZI, Bolum 3 (Hybrid Retriever): UCU DE varsayilan None/False --
        # verilmezse (mevcut tum cagirici) davranis BIREBIR eskisi gibidir (saf lexical).
        # Ders secimi ve site lexical kapilarindan gelen adaylari birlikte siralar;
        # yeni aday eklemez, site coverage/phrase_ok kapilarini gevsetmez.
        self._embedding_client = embedding_client
        self._embedding_cache = embedding_cache
        self.hybrid_enabled = bool(hybrid_enabled)
        self.last_metrics = {}

    # --- toplama -----------------------------------------------------------------
    def gather(self, question, domain, current=False, course_limit=3, site_limit=3):
        """Soruya en uygun kanıtları getirir.

        current=True (güncel mevzuat/oran sorusu): site sayfaları öne alınır, ders notları destek olur.
        """
        self.last_metrics = {"retrieval_mode": "lexical", "lexical_candidate_count": 0,
                             "semantic_used": False, "cache_hits": 0, "cache_misses": 0,
                             "fallback_reason": None, "embedding_attempted": False,
                             "embedding_success": False, "lexical_order": (), "semantic_order": ()}
        course = self._course_evidence(question, domain, course_limit)
        sites = self._site_evidence(question, site_limit) if domain in ("accounting", "general") else []
        items = (sites + course) if current else (course + sites)
        self.last_metrics["lexical_candidate_count"] = len(items)
        ranked = self._semantic_rerank(question, items)
        # Keep the original source priority: stable knowledge first for stable questions.
        return sorted(ranked, key=lambda item: (item.kind != "site") if current else (item.kind == "site"))

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

    def _semantic_rerank(self, question, items):
        """Yalniz zaten lexical kapiden (coverage/phrase_ok) GECMIS `items` arasinda
        yeniden-siralama yapar -- hicbir yeni oge eklemez/cikarmaz, hicbirini elemez.
        `hybrid_enabled=False`, embedding istemcisi verilmemis ya da hazir degilse (Ollama
        bu bilgisayarda kapali/erisilemez) sessizce, DOKUNMADAN orijinal sirayla geri
        doner -- ASLA hata firlatmaz veya cevap akisini kesmez."""
        if not self.hybrid_enabled or not items or self._embedding_client is None:
            self.last_metrics.update(retrieval_mode="lexical", semantic_used=False)
            return items
        self.last_metrics.update(embedding_attempted=True, embedding_success=False,
                                 lexical_order=tuple(item.label for item in items))
        started = time.perf_counter()
        self._embedding_deadline = started + float(getattr(self._embedding_client, "timeout", 90))
        try:
            if not self._embedding_client.is_ready():
                raise ValueError("embedding_not_ready")
            q_vector = self._embed_cached(question)
            if q_vector is None:
                raise ValueError("embedding_unavailable")
            scored = [(self._similarity(q_vector, item.text), item) for item in items]
            if any(similarity is None for similarity, _ in scored):
                raise ValueError("incomplete_embeddings")
        except Exception as exc:
            self.last_metrics.update(retrieval_mode="lexical", semantic_used=False,
                                     fallback_reason=type(exc).__name__)
            return items
        finally:
            self.last_metrics["semantic_ms"] = round((time.perf_counter() - started) * 1000, 3)
        scored.sort(key=lambda pair: (pair[0] is None, -(pair[0] or 0.0)))
        self.last_metrics.update(retrieval_mode="hybrid", semantic_used=True, embedding_success=True,
                                 semantic_order=tuple(item.label for _, item in scored))
        return [item for _, item in scored]

    def _similarity(self, q_vector, text):
        vector = self._embed_cached(text)
        return self._cosine(q_vector, vector) if vector is not None else None

    def _embed_cached(self, text):
        model_name = self._embedding_client.model_name
        if hasattr(self._embedding_client, "cache_identity"):
            model_name = self._embedding_client.cache_identity()
        if self._embedding_cache is not None and model_name is not None:
            cached = self._embedding_cache.get(model_name, text)
            if cached is not None:
                self.last_metrics["cache_hits"] = self.last_metrics.get("cache_hits", 0) + 1
                return cached
        self.last_metrics["cache_misses"] = self.last_metrics.get("cache_misses", 0) + 1
        remaining = getattr(self, "_embedding_deadline", time.perf_counter() + 90) - time.perf_counter()
        if remaining <= 0:
            return None
        original_timeout = getattr(self._embedding_client, "timeout", None)
        if original_timeout is not None:
            self._embedding_client.timeout = min(original_timeout, remaining)
        try:
            vector = self._embedding_client.embed(text)
        finally:
            if original_timeout is not None:
                self._embedding_client.timeout = original_timeout
        if vector is not None and self._embedding_cache is not None and model_name is not None:
            self._embedding_cache.put(model_name, text, vector)
        return vector

    @staticmethod
    def _cosine(a, b):
        if not a or not b or len(a) != len(b) or not all(math.isfinite(x) for x in [*a, *b]):
            return None
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return None
        return sum(x * y for x, y in zip(a, b)) / (norm_a * norm_b)

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
    def _terms(question, ignore_frame=False):
        """`ignore_frame=True`: soru İSKELETİ sözcükleri gerekli terim sayılmaz (yalnız
        `extractive_answer` kapısı bunu ister; `coverage()`'ın varsayılan anlamı -- research
        verifier/extractor gibi diğer tüketiciler dahil -- DEĞİŞMEDİ)."""
        seen, terms, previous = set(), [], None
        for t in tokens_tr(question):
            is_frame = ignore_frame and _frame_term(t, previous)
            previous = t
            if t not in STOP_WORDS and t not in FILLER and len(t) > 2 and t not in seen and not is_frame:
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
        term_stem = _match_key(term)

        def same(word):
            return word == term or _match_key(word) == term_stem
        positions = [i for i, w in enumerate(words) if same(w)]
        # Tireli bileşikler ('Bağ-Kur' -> 'bag','kur') soruda bitişik ('Bağkur') yazılabilir.
        for i in range(len(words) - 1):
            if i not in positions and same(words[i] + words[i + 1]):
                positions.append(i)
        return sorted(positions)

    @staticmethod
    def coverage(question, text, ignore_frame=False):
        """Sorudaki anlamlı kelimelerin kaçının metinde geçtiği (0..1)."""
        terms = Retriever._terms(question, ignore_frame=ignore_frame)
        if not terms:
            return 0.0
        words = tokens_tr(text)
        return sum(1 for t in terms if Retriever._positions(t, words)) / len(terms)

    @staticmethod
    def phrase_ok(question, text, window=5, ignore_frame=False):
        """Metinde bulunan soru kelimeleri, sorudaki sıraya yakın komşuluklarla birlikte mi geçiyor?

        'kurumlar vergisi oranı' sorusu için 'kurumlar vergisi beyannamesi ... yeniden değerleme oranı'
        gibi kelimeleri uzak yerlerde geçen alakasız bir paragraf reddedilir."""
        terms = Retriever._terms(question, ignore_frame=ignore_frame)
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
            if (Retriever.coverage(question, probe, ignore_frame=True) >= min_coverage
                    and Retriever.phrase_ok(question, probe, window=5 if strict else 12, ignore_frame=True)):
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
