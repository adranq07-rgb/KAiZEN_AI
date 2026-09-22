"""Kaizen'in karar mekanizması.

Bir soru geldiğinde sırayla şunlar denenir (ilk cevap veren kazanır):

  1. Kullanıcının daha önce düzelttiği cevap            (kesin)
  2. Matematik / hesaplayıcılar / yevmiye / hesap planı   (kesin, modelsiz, uydurma yok)
  3. Yıllık parametre kayıt defteri (süzgeçten geçmiş)    (kaynaklı, en yeni yıl)
  4. Yerel hafıza: ders notları + toplanan site sayfaları (model varsa yorumlar, yoksa alıntılar)
  4b. Daha önce araştırmayla öğrenilmiş bilgi kartı (memory/knowledge_cards.py) - varsa araştırmaya gerek kalmaz
  5. Araştırma zinciri (Hermes, ya da onun yerini alacak başka bir sağlayıcı) - yalnız yerel hafızada bulunamazsa
  6. Dürüst "bulamadım" cevabı

Hermes/model kapalı olsa bile 1-4b çalışır: Kaizen'in bağımsızlığı buradan gelir.

Kendi kendini geliştiren beyin: araştırma zinciri bir soruyu başarıyla cevapladığında (adım 5),
cevap "bilgi kartı" olarak süzgeçten geçirilip kalıcı hafızaya işlenir (`_remember_research`).
İlk öğrenildiğinde kart "beklemede"dir (adım 4b'de uyarı notuyla kullanılır); mali müşavir
`onayla: <soru>` komutuyla onaylayınca kart kalıcı ders notuna (adım 4) dönüşür ve bir daha
araştırmaya gerek kalmaz. Ayrıca her yeni bilgi, süzgeçten geçmiş parametre defteriyle
(`accounting/facts.py`) çapraz kontrol edilir; çelişki varsa işaretlenir (`cards.contradictions()`).

Mimari not (BrainManager, Kademe 1): Bu sınıf artık dört ayrı hafıza deposunu
(learning_store, site_store, facts, cards) doğrudan kendi içinde tutup her birine tek tek
dokunmuyor; hepsi tek bir `memory/brain_manager.py::BrainManager` örneğinde (`self.brain`)
toplanmış durumda. `KaizenBrain` yalnızca `self.brain`'in arayüzüyle konuşur; hafıza
altyapısı ileride değişirse (ör. bir embedding/vector veritabanı eklenirse) yalnızca
`BrainManager`'ın içi değişir, bu sınıfın karar mantığı aynı kalır. (Kapsam dışı: `AccountingAgent`'ın
kendi küçük JSON düzeltme deposu -- bkz. brain_manager.py modül docstring'i.)
"""
import re
from datetime import date

from accounting.calculators import CalculatorRouter
from accounting.chart_of_accounts import ChartOfAccounts
from accounting.journal import JournalRouter
from accounting.retriever import says_not_found
from core.ai.fallback_provider import is_failure
from core.math_calculator import DecimalCalculator, MathCalculationError
from core.text_tr import fold_tr, format_decimal_tr, parse_tr_number
from memory.brain_manager import BrainManager

_ARITHMETIC = re.compile(r"[\d\s,.+\-*/%()^x×÷]+")


class KaizenBrain:
    CURRENT_TERMS = {
        "guncel", "mevzuat", "oran", "sinir", "limit", "teblig", "kanun", "asgari",
        "2024", "2025", "2026", "2027", "2028", "bu yil", "yeni yil", "haddi", "tavan", "tutar",
    }
    ACCOUNTING_TERMS = {
        "muhasebe", "fatura", "yevmiye", "bilanco", "vergi", "kdv", "gelir", "gider", "amortisman",
        "hesap kodu", "tek duzen", "tekduzen", "tdhp", "maliyet", "bordro", "defter", "donem sonu",
        "kapanis", "mizan", "kasa hesab", "banka hesab", "alacak", "borc", "stopaj", "damga",
        "beyanname", "sgk", "kidem", "ihbar", "tevkifat", "stok", "envanter", "cari", "smmm", "ymm",
        "serbest meslek", "makbuz", "asgari ucret", "binek", "kurumlar", "e-fatura", "efatura",
        "e-arsiv", "e-defter", "ticari kazanc", "ortaklar cari", "kambiyo", "reeskont", "karsiligi",
        "kayit", "kaydi", "kar payi", "sermaye", "tazminat", "bilanco", "gelir tablosu", "mali musavir",
        "tevkifat", "prim", "hesap plani", "iade", "vade", "senet", "cek ", "ortak",
    }
    OFFICE_TERMS = {
        "excel", "formul", "word", "pdf", "powerpoint", "ofis", "calisma kitabi", "hucre", "pivot",
        "dusey", "duseyara", "xlookup", "coketopla", "topla(", "makro", "sayfa duzeni", "icindekiler",
    }

    def __init__(self, provider, accounting_agent, learning_store=None, site_store=None,
                 facts=None, chart=None, cards=None, exam_candidates_path=None, brain_manager=None):
        self.provider = provider
        self.accounting_agent = accounting_agent
        # BrainManager: hafıza sistemleri için TEK erişim noktası (bkz. memory/brain_manager.py).
        self.brain = brain_manager or BrainManager(
            learning_store=learning_store, site_store=site_store, facts=facts,
            cards=cards, exam_candidates_path=exam_candidates_path,
        )
        self.calculator = DecimalCalculator()
        self.chart = chart or ChartOfAccounts()
        self.calculators = CalculatorRouter()
        self.journal = JournalRouter(self.chart)
        self._research_cache = (None, None)
        self.last_route = None  # hangi yolla cevaplandığı (test ve hata ayıklama için)

    # --- sınıflandırma -------------------------------------------------------------
    @staticmethod
    def _normalized(message):
        return fold_tr(message)

    @classmethod
    def classify(cls, message):
        normalized = cls._normalized(message)
        if normalized.startswith("muhasebe:") or any(term in normalized for term in cls.ACCOUNTING_TERMS):
            return "accounting"
        if any(term in normalized for term in cls.OFFICE_TERMS):
            return "office"
        body = normalized.removeprefix("matematik:").strip()
        if normalized.startswith("matematik:") or _ARITHMETIC.fullmatch(body):
            return "mathematics"
        return "general"

    @classmethod
    def needs_current_research(cls, message):
        normalized = cls._normalized(message)
        current_year = str(date.today().year)
        words = re.findall(r"[a-z0-9]+", normalized)
        return current_year in normalized or any(
            (term in normalized) if " " in term else any(w.startswith(term) for w in words)
            for term in cls.CURRENT_TERMS
        )

    @staticmethod
    def _source_label(row):
        return f"{row['subject']} — {row.get('section') or row.get('locator') or 'bölüm'}"

    # --- 1. kullanıcı düzeltmesi -----------------------------------------------------
    def _correction(self, question):
        # Kapsam dışı (Kademe 1, bilinçli): AccountingAgent'ın kendi düzeltme deposu (JSON)
        # henüz BrainManager'a taşınmadı -- bkz. memory/brain_manager.py modül docstring'i.
        memory = getattr(self.accounting_agent, "learning_memory", None)
        if memory is None:
            return None
        wanted = fold_tr(question)
        try:
            for record in reversed(memory.get_all()):
                if fold_tr(record["question"]) == wanted:
                    return ("KULLANICININ SON DÜZELTMESİ (güncelliği yeniden doğrulanmadı):\n"
                            f"{record['correct_answer']}")
        except Exception:
            return None
        return None

    # --- 2. kesin araçlar --------------------------------------------------------------
    def _arithmetic(self, question):
        expression = question.strip()
        if not _ARITHMETIC.fullmatch(expression) or not re.search(r"\d", expression):
            return None
        if not re.search(r"[+\-*/%^x×÷]", expression):
            return None
        prepared = expression.replace("×", "*").replace("÷", "/").replace("^", "**")
        prepared = re.sub(r"(?<=[\d)\s])x(?=[\d(\s])", "*", prepared)
        prepared = re.sub(r"\d[\d.,]*", lambda m: str(parse_tr_number(m.group())), prepared)
        try:
            result = self.calculator.calculate(prepared)
        except MathCalculationError as exc:
            return f"Kaizen: {exc}"
        return f"SONUÇ: {format_decimal_tr(result)}"

    def _exact_tools(self, question):
        for route, tool in (
            ("journal", self.journal.answer),
            ("calculator", self.calculators.answer),
            ("chart", self.chart.answer),
        ):
            try:
                result = tool(question)
            except Exception as exc:  # bir aracın hatası diğer yolları kapatmasın
                result = f"Kaizen: {route} aracı hata verdi: {type(exc).__name__}: {exc}"
            if result:
                self.last_route = route
                return result
        return None

    # --- 4. yerel hafıza -----------------------------------------------------------------
    def _grounded_answer(self, question, domain, evidence):
        prompt = self.brain.build_prompt(question, domain, evidence)
        try:
            answer = self.provider.ask(prompt)
        except Exception as exc:
            answer = f"Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod) -> {type(exc).__name__}"
        if is_failure(answer):
            return None
        if says_not_found(answer):
            return "NOT_FOUND"
        sources = self.brain.sources_block(evidence)
        if sources and "KAYNAKLAR" not in answer:
            answer = f"{answer}\n\n{sources}"
        return answer

    @staticmethod
    def _research_failed(text):
        return (not text) or is_failure(text) or text.startswith("Kaizen:")

    def _research_once(self, question):
        """Araştırma zincirini soru başına en çok bir kez çalıştırır (Hermes çağrısı pahalı).

        Başarılı sonuç, kendi kendini geliştiren beyin tarafından bilgi kartı olarak hafızaya işlenir
        (`_remember_research`); bir dahaki sefere aynı/benzer soru için araştırmaya gerek kalmayabilir.
        """
        if self._research_cache[0] != question:
            result = self.accounting_agent.ask(question)
            if not self._research_failed(result):
                self._remember_research(question, result)
            self._research_cache = (question, result)
        return self._research_cache[1]

    # --- kendi kendini geliştiren beyin: araştırmayı kalıcı hafızaya işleme --------------------
    def _remember_research(self, question, answer_text):
        """Araştırma (Hermes ya da yarın onun yerini alacak başka bir sağlayıcı — Kaizen için o yalnız
        bir 'işçi') bir soruyu cevapladığında, bu sonuç HER ZAMAN Kaizen'in kendi kalıcı hafızasına
        işlenir; beklemede/doğrulanmış ayrımı yalnız cevabın güven etiketini belirler, hafızaya
        yazılıp yazılmayacağını değil. Böylece Hermes kapansa/değişse bile öğrenilen bilgi kaybolmaz.

        Kart oluşturma, çapraz kontrol, kalıcı hafızaya işleme ve sınav önerisi artık
        BrainManager'ın işi (bkz. memory/brain_manager.py::remember_research)."""
        return self.brain.remember_research(question, answer_text)

    def confirm_card(self, question):
        """Mali müşavirin `onayla: <soru>` komutuyla bekleyen bir kartı elle onaylaması."""
        return self.brain.confirm_card(question)

    def _card_fallback(self, question, domain):
        """Daha önce araştırmayla öğrenilmiş bir bilgi kartı varsa (doğrulanmamış olsa bile) onu döner."""
        card = self.brain.recall_card(question)
        if card is None:
            return None, False
        self.last_route = "memory_card_confirmed" if card["status"] == "confirmed" else "memory_card_pending"
        note = "" if card["status"] == "confirmed" else (
            "NOT: Bu bilgi tek bir araştırma turundan öğrenildi, henüz ikinci bağımsız doğrulama görmedi "
            "(mali müşavir 'onayla: <soru>' ile onaylayabilir).\n\n")
        text = f"{note}Kaizen (önceki araştırmadan öğrenilmiş bilgi):\n{card['answer']}\n\nKAYNAK: {card['source_label']}"
        return text, False

    def _from_memory(self, question, domain, current):
        """Yerel hafızadan cevap. Güncel bir soruda toplanmış site kanıtı yoksa önce araştırma denenir."""
        evidence = self.brain.gather_evidence(question, domain, current)
        stale_note = ""
        if current and domain == "accounting" and not any(e.kind == "site" for e in evidence):
            self.last_route = "research"
            researched = self._research_once(question)
            if not self._research_failed(researched):
                return researched, False
            if not evidence:
                return self._card_fallback(question, domain)
            stale_note = ("NOT: Güncel kaynak doğrulanamadı; aşağıdaki bilgi ders notlarından geliyor "
                          "ve güncel olmayabilir.\n\n")
        if not evidence:
            return self._card_fallback(question, domain)
        answer = self._grounded_answer(question, domain, evidence)
        if answer == "NOT_FOUND":
            fallback, _ = self._card_fallback(question, domain)
            return (fallback, False) if fallback else (None, True)
        if answer is None:  # model yok: kanıttan düz cevap (soruyla yeterince örtüşmüyorsa vermez)
            extractive = self.brain.extractive_answer(question, evidence, strict=current)
            if extractive is None:
                return self._card_fallback(question, domain)
            self.last_route = "memory_extractive"
            return stale_note + extractive, False
        self.last_route = "memory_grounded"
        return stale_note + answer, False

    # --- ana giriş -------------------------------------------------------------------------
    def answer(self, message):
        self.last_route = None
        self._research_cache = (None, None)
        lowered = message.casefold().lstrip()
        prefixed = lowered.startswith("muhasebe:") or lowered.startswith("matematik:")
        question = message.split(":", 1)[1].strip() if ":" in message and prefixed else message.strip()
        domain = self.classify(message)

        if not question:
            self.last_route = "empty"
            return "Kaizen: Muhasebe sorusu bos olamaz." if lowered.startswith("muhasebe") else "Kaizen: Soru bos olamaz."

        corrected = self._correction(question)
        if corrected:
            self.last_route = "correction"
            return corrected

        arithmetic = self._arithmetic(question)
        if arithmetic:
            self.last_route = "arithmetic"
            return arithmetic

        exact = self._exact_tools(question)
        if exact and exact.startswith("Kaizen: Tutarı belirtmediniz") and self.last_route == "journal":
            # Tutarsız kayıt sorusu: önce kavramsal cevabı (öğretilmiş şablon/ders notu) dene, sonra tutar iste
            explained, _ = self._from_memory(question, "accounting", False)
            if explained and self.last_route.startswith("memory"):
                return explained + "\n\nNOT: Tutarı (ve varsa KDV oranını) yazarsan kaydı rakamlarla, kuruşu kuruşuna çıkarırım."
            self.last_route = "journal"
        if exact:
            return exact

        current = self.needs_current_research(question)
        fact = self.brain.verified_fact_answer(question)
        if fact:
            self.last_route = "facts"
            return fact

        if domain == "general":
            self.last_route = "provider"
            reply = self.provider.ask(message)
            if is_failure(reply):  # model kapalı: yine de yerel hafızada ilgili kayıt var mı?
                remembered, _ = self._from_memory(question, "general", current)
                return remembered or reply
            return reply

        memory_answer, model_said_missing = self._from_memory(question, domain, current)
        if memory_answer:
            return memory_answer

        if domain == "accounting":
            self.last_route = "research"
            researched = self._research_once(question)
            if is_failure(researched):
                self.last_route = "not_found_offline"
                return ("Kaizen: Bu soruyu yerel hafızamda bulamadım ve araştırma modeli şu an kullanılamıyor. "
                        "'güncelle' komutuyla güvenilir siteleri tarayıp hafızamı güncelleyebilirsin; "
                        "cevabı uydurmayacağım.")
            return researched
        if domain == "office":
            self.last_route = "office_missing"
            return ("Kaizen: Bu ofis konusu için yerel hafızada doğrulanmış bilgi yok. "
                    "İşlem veya formül uydurmayacağım; kaynak eklendiğinde öğrenirim.")
        self.last_route = "provider"
        return self.provider.ask(message)
