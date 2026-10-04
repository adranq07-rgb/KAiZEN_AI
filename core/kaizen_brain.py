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
import time
from datetime import date

from accounting.calculators import CalculatorRouter
from accounting.chart_of_accounts import ChartOfAccounts
from accounting.journal import JournalRouter
from accounting.retriever import says_not_found
from core.ai.fallback_provider import is_failure
from core.math_calculator import DecimalCalculator, MathCalculationError
from core.text_tr import fold_tr, format_decimal_tr, parse_tr_number
from core.trace import (
    KaizenTrace, ROUTE_CONFIDENCE, UNKNOWN, CONFLICTED,
    REFUSAL_CURRENT_FACT_MISSING, REFUSAL_EMPTY_QUESTION, REFUSAL_MODEL_UNAVAILABLE,
    REFUSAL_RESEARCH_FAILED, REFUSAL_RETRIEVAL_NO_MATCH, REFUSAL_RETRIEVAL_THRESHOLD_FAILED,
)
from memory.brain_manager import BrainManager
from learning.principle_retriever import HIGH as _PRINCIPLE_HIGH, MEDIUM as _PRINCIPLE_MEDIUM
from learning.principle_discovery import PrincipleDiscoveryEngine, DiscoveredPrinciple
from learning.question_profile import explicit_years, profile_question
from learning.strategy_advisor import StrategyAdvisor
from learning.trace_bridge import fill_principle_trace
from research.engine import run_research
from research.scrapling_adapter import get_adapter
from research.models import PARTIAL as _RESEARCH_PARTIAL
from research.models import SUPPORTED as _RESEARCH_SUPPORTED
from research.summary import summarize_research
from accounting.document_reconciliation import reconcile_document_entry
from accounting.receivable_collection import reconcile_receivable_collection

_ARITHMETIC = re.compile(r"[\d\s,.+\-*/%()^x×÷]+")


def _format_research_result(result):
    """`research.models.ResearchResult` -> Kaizen'in mevcut araştırma cevabı BİÇEMİNE
    (bkz. `accounting/facts.py::FactRegistry._answer_topic` -- "SONUÇ:"/"DOĞRULAMA:"/
    "KAYNAKLAR:" satırları) uyan bir metin. madde 13/27 (KIRMIZI ÇİZGİ): yalnızca
    `status == SUPPORTED` VE en az bir `verified_claims` varsa bir metin döner -- PARTIAL/
    CONFLICTED/INSUFFICIENT/SEARCH_DEGRADED/SEARCH_UNAVAILABLE dahil HER ŞEY None döner
    (çağıran Hermes'e düşer). Asla "VERIFIED" kelimesi kullanılmaz (o etiket yalnız
    `core/trace.py`'nin kesin-araç rotasına ait, madde 13).

    TRUSTED SOURCE POLİTİKASI (EK DÜZELTME):
    - Resmî kaynak (priority=1) ERİŞİLEBİLİRSE -> "resmî kaynaklarda teyit edildi"
    - Resmî kaynak ERİŞİLEMEZSE ama 2+ mesleki/ikincil kaynak (priority=2/3) uzlaşıyorsa ->
      "mesleki/ikincil güvenilir kaynaklarda teyit edildi (resmî kaynak erişilemedi)"
    - Resmî kaynak GERÇEKTEN okunmadıysa "resmî olarak doğruldu" GÖSTERİLMEZ
    """
    claims = result.verified_claims
    partial_note = ""
    if result.status == _RESEARCH_PARTIAL and not result.conflicts:
        # Cevap-verme düzeltmesi (2026-10-03): plan, kullanıcının sorusunu birden fazla ARAMA
        # AÇISINA (soru + resmî-domain + Resmî Gazete) böler; bu açılardan yalnız bir kısmı
        # destek bulunca genel durum PARTIAL olur ve -- kullanıcının sorusunun KENDİSİ resmî /
        # 2+ bağımsız kaynakla SUPPORTED claim aldığı halde -- cevap tamamen reddediliyordu.
        # Burada yalnız o SUPPORTED claim'ler (çelişki YOK şartıyla; claim zaten resmî veya
        # 2+ bağımsız kaynak + dönem + alaka kapısından geçmiştir) sunulur; eksik kalan açılar
        # cevapta dürüstçe belirtilir. Claim yoksa / çelişki varsa eski davranış (red) aynen sürer.
        claims = tuple(c for c in result.verified_claims if c.text.startswith(result.question))
        if claims:
            partial_note = ("NOT: Bu cevap yalnız aşağıdaki kaynaklarda teyit edilen kısmı kapsar; "
                            f"{len(result.missing_information) + len(result.verified_claims) - len(claims) or 'bazı'} "
                            "ek doğrulama açısı tamamlanamadı. Karar vermeden önce kaynağı kontrol edin.")
    elif result.status != _RESEARCH_SUPPORTED:
        return None
    if not claims:
        return None
    evidence_by_id = {e.evidence_id: e for e in result.evidence}
    lines = []
    for claim in claims:
        lines.append(f"SONUÇ: {claim.text}: {claim.value}" if claim.value else f"SONUÇ: {claim.text}")
        supporting = [evidence_by_id[eid] for eid in claim.supporting_evidence_ids if eid in evidence_by_id]
        # Kaynak türlerini ayır: resmî vs mesleki/ikincil
        official_sources = sorted({e.source_name or e.domain for e in supporting
                                   if e.has_real_content() and e.official})
        professional_sources = sorted({e.source_name or e.domain for e in supporting
                                       if e.has_real_content() and not e.official})
        if official_sources:
            lines.append(f"DOĞRULAMA: {', '.join(official_sources)} resmî kaynaklarında teyit edildi.")
        elif professional_sources:
            lines.append(f"DOĞRULAMA: {', '.join(professional_sources)} mesleki/ikincil güvenilir kaynaklarında teyit edildi (resmî kaynak erişilemedi).")
        from accounting.retriever import Retriever
        with_passage = [e for e in supporting if e.passage]
        # En alakalı pasaj: resmî kaynak öncelikli, sonra soruya en yüksek örtüşme (ilk gelen değil).
        best_ev = max(with_passage, key=lambda e: (bool(e.official), Retriever.coverage(result.question, e.passage)),
                      default=None)
        passage = best_ev.passage if best_ev is not None else ""
        if passage:
            lines.append(f"KANIT: {passage}")
    if partial_note:
        lines.append(partial_note)
    if result.sources:
        lines.append("KAYNAKLAR: " + " ; ".join(result.sources[:4]))
    return "\n".join(lines)


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
        # SGK statü/kurum kavramları ('sgk' kelimesi geçmese de sosyal güvenlik = muhasebe/bordro alanı)
        "bagkur", "bag-kur", "ssk", "emekli sandigi", "sigortali", "sigortalilik", "isveren payi",
        "prime esas", "hizmet akdi",
    }
    OFFICE_TERMS = {
        "excel", "formul", "word", "pdf", "powerpoint", "ofis", "calisma kitabi", "hucre", "pivot",
        "dusey", "duseyara", "xlookup", "coketopla", "topla(", "makro", "sayfa duzeni", "icindekiler",
    }

    def __init__(self, provider, accounting_agent, learning_store=None, site_store=None,
                 facts=None, chart=None, cards=None, exam_candidates_path=None, brain_manager=None,
                 log_dir=None, principle_retriever=None, learning_brain_enabled=False,
                 search_provider=None, research_fetcher=None, research_engine_enabled=False,
                 reflection_lifecycle=None, strategy_advisor=None, runtime_learning=None,
                 strict_fact_safety=False,
                 principle_discovery_enabled=False,
                 principle_discovery_min_support=3, general_accounting_model_answer=False):
        self.provider = provider
        self.accounting_agent = accounting_agent
        # KAIZEN BUYUK GELISTIRME PAKETI #1, Faz C (madde 13): Learning Brain / Principle Layer,
        # kontrollu (feature-flag'li) entegrasyon. Her ikisi de varsayilan olarak BOS/KAPALI --
        # bu constructor'i cagiran MEVCUT HICBIR test/kod (principle_retriever/learning_brain_enabled
        # vermeyen) davranisini BIREBIR korur (bkz. core/trace.py principle_* alanlarinin
        # "SHADOW MODE'da varsayilan bos" testi -- bu davranis burada da BOZULMAZ).
        self._principle_retriever = principle_retriever
        self.learning_brain_enabled = bool(learning_brain_enabled)
        # KAIZEN BUYUK IS EMRI #21: Brain v2 - Autonoum Prinsip Bulma Motoru
        # Feature flag ile kapali/acik -- mevcut koddaki herhangi bir testi kirmadan
        # kapaliyla baslayip yanlisici olarak aktif edilebilir.
        self.principle_discovery_enabled = bool(principle_discovery_enabled)
        self.principle_discovery_min_support = int(principle_discovery_min_support)
        # Principle registry - brain manager'dan elde edilir (varsa)
        self._principle_registry = getattr(brain_manager, 'registry', None) if brain_manager else None
        if self.principle_discovery_enabled:
            from learning.principle_discovery import PrincipleDiscoveryEngine
            # Use brain_manager's registry/refl_store if available; otherwise
            # the engine will use whatever registry is passed (it may be None, which
            # is OK -- discovery may be a no-op until principles are loaded).
            _reg = self._principle_registry if self._principle_registry is not None else getattr(brain_manager, 'registry', None) if brain_manager else None
            _rs = getattr(brain_manager, 'refl_store', None) if brain_manager else None
            _bm = brain_manager
            self._principle_discovery = PrincipleDiscoveryEngine(
                principle_registry=_reg,
                store=_rs,
                brain_manager=_bm,
                min_independent=self.principle_discovery_min_support,
            )
        else:
            self._principle_discovery = None
        # KAIZEN BUYUK IS EMRI #2, Faz 28-31 (madde 28-31): Research Engine, AYNI disiplinle
        # (Learning Brain ile BIREBIR ayni desen) kontrollu entegrasyon. `research_engine_enabled`
        # VE `search_provider` (ikisi de) varsayilan olarak KAPALI/None -- bu constructor'i cagiran
        # MEVCUT HICBIR test/kod (bu iki alani vermeyen) davranisini BIREBIR korur: `_research_once`
        # dogrudan (eskisi gibi) Hermes'e (accounting_agent.ask) gider, Research Engine hic
        # CAGRILMAZ bile (bkz. _research_engine_once). Acmak/kapatmak tek satirlik
        # config/Kaizen.json degisikligi (research.research_engine_enabled) -- kod degismez.
        self._search_provider = search_provider
        self.research_engine_enabled = bool(research_engine_enabled)
        self._research_fetcher = research_fetcher  # None ise ilk kullanimda tembel (lazy) kurulur
        # Learning Loop fazı: Reflection/Experience yaşam döngüsü. İKİSİ DE varsayılan None --
        # verilmezse (mevcut tüm testler/çağrılar) davranış BİREBİR eskisi gibidir. KaizenBrain
        # ReflectionStore'a DOĞRUDAN dokunmaz; yalnız `reflection_lifecycle` cephesini (kayıt +
        # onayla:/düzelt: geri bildirimi) ve `strategy_advisor`'ı (onaylı deneyimden SÜREÇ
        # ipucu, asla FACT) kullanır. Öncelik sırası DEĞİŞMEZ: deneyim en erken, düzeltme/kesin
        # araç/FactRegistry/kanıtlı hafıza katmanları GEÇİLDİKTEN sonra devreye girer.
        self._reflection_lifecycle = reflection_lifecycle
        self._strategy_advisor = strategy_advisor
        self._runtime_learning = runtime_learning
        self.strict_fact_safety = strict_fact_safety
        self.general_accounting_model_answer = bool(general_accounting_model_answer)
        self._last_reasoning_context = None
        # Accountant Reasoning Core v1: muhasebe soruları için structured reasoning context
        from core.accounting_reasoning import AccountantReasoningEngine
        self._reasoning_engine = AccountantReasoningEngine(
            learning_store=learning_store if learning_store is not None else getattr(brain_manager, "learning_store", None),
            principle_retriever=principle_retriever,
            accounting_brain=getattr(brain_manager, 'accounting_brain', None) if brain_manager else None,
        )
        self._current_advice = None
        self._last_research_meta = None   # yalnız Research Engine GERÇEKTEN çalıştıysa dolu
        self.last_feedback_effect = None
        # BrainManager: hafıza sistemleri için TEK erişim noktası (bkz. memory/brain_manager.py).
        self.brain = brain_manager or BrainManager(
            learning_store=learning_store, site_store=site_store, facts=facts,
            cards=cards, exam_candidates_path=exam_candidates_path, log_dir=log_dir,
        )
        self.calculator = DecimalCalculator()
        self.chart = chart or ChartOfAccounts()
        self.calculators = CalculatorRouter()
        self.journal = JournalRouter(self.chart, principle_registry=getattr(principle_retriever, "registry", None))
        self._research_cache = (None, None)
        self._last_research_via = None  # "engine" | "hermes" | None -- yalnız gözlem/test için
        self.last_route = None  # hangi yolla cevaplandığı (test ve hata ayıklama için)
        # İş emri (2026-09-23, "RAG v2 - Faz 1"): cevap zincirinin görünürlüğü. Kullanıcıya giden
        # METİN cevabı hiç değişmez -- bu, self.last_route ile AYNI desende, çağrıdan SONRA
        # `brain.last_trace` üzerinden okunan AYRI bir alan (bkz. core/trace.py::KaizenTrace).
        self.last_trace = None

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
        # Açık takvim yılı (herhangi bir yıl): yıla bağlı parametre/mevzuat sorusu, sorulan DÖNEME
        # özgü kaynak gerektirir -- yıl hard-code edilmez, sorudan okunur (bkz. question_profile).
        return current_year in normalized or bool(explicit_years(message)) or any(
            (term in normalized) if " " in term else any(w.startswith(term) and not (term == "tutar" and w.startswith("tutarl")) for w in words)
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
        # A calendar year alone is not a calculation amount. Parameter lookups must
        # reach FactRegistry / Research rather than asking the user to supply the rate.
        from accounting.calculators import _extract
        info = _extract(question)
        years = set(explicit_years(question))
        only_year_amounts = not any(a not in years for a in info["amounts"])
        if self.needs_current_research(question) and only_year_amounts and not info["rates"]:
            return None
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
                if route == "journal" and self.journal.last_result:
                    state = self.journal.last_result
                    self.last_trace.accounting_pipeline = state
                    self.last_trace.journal_entry = state.get("journal")
                    self.last_trace.invariant_failures = state.get("invariant_failures", [])
                    self.last_trace.missing_facts = state.get("missing_information", [])
                    self.last_trace.principle_ids = tuple(p["principle_id"] for p in state.get("principles", []))
                    self.last_trace.deterministic_tool_used = state.get("status") == "VALID"
                    self.last_trace.current_fact_needed = bool(state.get("knowledge_types", {}).get("current"))
                    if self._reasoning_engine is not None:
                        context = self._reasoning_engine.apply_journal_result(self._last_reasoning_context, state)
                        self._last_reasoning_context = context
                        self.last_trace.accounting_reasoning_used = True
                        self.last_trace.accounting_reasoning_context = context.to_dict()
                        self.last_trace.problem_type = context.problem_type
                        self.last_trace.knowledge_source_types = context.knowledge_sources
                    if state.get("status") != "VALID":
                        self.last_route = "accounting_clarification" if state.get("status") == "CLARIFICATION" else "accounting_invalid"
                        self.last_trace.refusal_reason = state.get("status")
                return result
        return None

    # --- Faz C (madde 13): Learning Brain / Principle Layer -- kontrollu entegrasyon --------
    def _maybe_augment_with_principle(self, question, domain, prompt):
        """KAIZEN BUYUK GELISTIRME PAKETI #1, Faz C1/C2/C3 (madde 13, birebir):

        - C1 (Shadow -> Assisted Mode): bu fonksiyon yalnizca `_grounded_answer` icinden,
          yani zaten yerel hafizada kanit (evidence) BULUNMUS ve modele gonderilecek bir
          prompt zaten INSA EDILMIS oldugunda cagrilir -- Principle Layer hicbir zaman TEK
          BASINA bir cevap yolu acmaz, yalnizca var olan bir cevabi INSA EDEN prompt'a
          YARDIMCI baglam ekler (madde 13: "reasoning aid, never the sole source of truth").
        - C2 (CONFIDENCE GATE): yalnizca HIGH/MEDIUM prompt'u etkiler; LOW/NONE ASLA cevabi
          etkilemez (fonksiyon prompt'u degistirmeden aynen doner) -- hicbir zaman zorla secim
          yapilmaz (retriever'in kendi madde 11 sozlesmesi zaten bunu garanti eder, burada
          AYRICA kontrol edilir).
        - C3 (FACT FIREWALL): bu yol yalnizca `_grounded_answer`'a ulasan sorularda calisir --
          yani `_correction`/`_arithmetic`/`_exact_tools`/`facts.verified_fact_answer` (kesin
          arac + parametre defteri) HEPSI BU FONKSIYONDAN ONCE calisip BULAMADI ise buraya
          gelinir (bkz. `_answer_core` sirasi). Boylece Principle Layer bir oran/tutar/tarih/
          SGK primi sorusuna ASLA cevap URETEMEZ -- yalnizca zaten var olan, ders notu/site
          kanitina dayali bir cevabi zenginlestirir. Route hala "memory_grounded" kalir
          (ROUTE_CONFIDENCE: SUPPORTED) -- principle katkisi cevabi ASLA VERIFIED yapmaz.

        Domain guvenlik siniri: yalnizca domain=='accounting' (ilkeler muhasebe ilkesidir;
        office/general/mathematics'te hic calismaz)."""
        if not self.learning_brain_enabled or self._principle_retriever is None or domain != "accounting":
            return prompt
        try:
            result = self._principle_retriever.retrieve(question)
        except Exception:
            return prompt
        # Gozlemlenebilirlik (Brain Inspector, Faz F2): confidence fark etmeksizin trace
        # doldurulur -- ama bu METIN CEVABI hic etkilemez (trace/cevap ayrimi, core/trace.py'nin
        # kurdugu invariant burada da gecerli).
        if self.last_trace is not None:
            fill_principle_trace(self.last_trace, result)
            self.last_trace.principle_candidate = result.selected or (
                result.candidates[0].principle_id if result.candidates else None)
        if result.confidence not in (_PRINCIPLE_HIGH, _PRINCIPLE_MEDIUM) or not result.selected:
            return prompt  # LOW/NONE (veya secim yok): madde 11/C2, cevap HIC etkilenmez
        principle = self._principle_retriever.registry.get(result.selected)
        if principle is None:
            return prompt
        caveat = (
            "kesin degil, tek basina kaynak degil"
            if result.confidence == _PRINCIPLE_HIGH else
            "kesin degil, birden fazla yakin aday ilke var, yalnizca destekleyici baglam"
        )
        hint = (
            f"\n\n[LEARNING BRAIN ILKE IPUCU -- {caveat}]\n"
            f"{principle['name']}: {principle['description']}\n"
            "Bu ipucunu yalniz yukaridaki KAYNAK metniyle tutarliysa kullan; kaynakla "
            "celisiyorsa veya sorudan bagimsizsa yok say, asla oran/tutar/tarih/mevzuat "
            "UYDURMA."
        )
        return prompt + hint

    # --- Learning Loop: onaylı deneyimden SÜREÇ ipucu ---------------------------------------
    def _advise_strategy(self, question, domain, current):
        """Deterministik katmanlar + FactRegistry GEÇİLDİKTEN sonra çağrılır (bkz. _answer_core).
        Deneyim asla cevap KAYNAĞI değildir: yalnız (a) prompt'a süreç ipucu ekler, (b) yapısal
        olarak "yıla bağlı güncel parametre" sorusuna araştırma tetiklemeyi öne çeker.
        Döner: (research_trigger_uygulandı_mı)."""
        self._current_advice = None
        if (self._strategy_advisor is None and self._runtime_learning is None) or domain != "accounting":
            return False
        try:
            advice = (self._runtime_learning.advise(question, domain, needs_current=current)
                      if self._runtime_learning is not None else
                      self._strategy_advisor.advise(question, domain, needs_current=current))
        except Exception:
            return False
        trace = self.last_trace
        if not advice.applied:
            if trace is not None and advice.rejected_reason:
                trace.experience_rejected_reason = advice.rejected_reason
            return False
        self._current_advice = advice
        if trace is not None:
            trace.experience_reusable = True
            trace.experience_advice = advice.strategy_kind
            trace.strategy = advice.strategy_kind
            trace.strategy_source = advice.source
            trace.strategy_experience_ids = advice.experience_ids
            trace.learned_principle_id = advice.policy_id

        # KAIZEN BUYUK IS EMRI #21, Faz 26: Brain v2 - Principle-based strategy guidance.
        # Zaten bir strateji önerisi varsa ilkeyi de katma (principle_selected_for_strategy zaten
        # _answer_core'da trace'e yazıldı). İlke strateji ipucunu prompt'a ekler ama ASLA fakt olarak.
        if (self.principle_discovery_enabled and self._principle_discovery is not None
                and self.last_trace.principle_selected_for_strategy and self._current_advice.applied):
            try:
                principle_hint = self._build_principle_strategy_hint()
                if principle_hint:
                    # Hint'i mevcut advice'e ekle
                    self._current_advice.guide = (
                        f"{self._current_advice.guide}\n\n"
                        f"[PRINCIPLE STRATEGY GUIDANCE] {principle_hint}"
                    )
                    # Trace'e de ek bilgi kaydet
                    if trace is not None:
                        trace.strategy_guidance_source = "principle"
            except Exception:
                pass  # Ilke ipucu hata verirse cevap bozulmaz

        return bool(advice.triggers_research and not current)

    def _build_principle_strategy_hint(self):
        """Retrieved active principle'ten strategi ipucu çıkar."""
        principle_id = self.last_trace.retrieved_principle_id
        if not principle_id:
            return None

        # Registry'den ilkeyi al (KaizenBrain'tan stored)
        principle = self._principle_registry.get(principle_id) if self._principle_registry else None
        if principle is None:
            return None

        # Strategy ipucu: ilkenin stratejistatement'inden
        strategy_stmt = principle.get("strategy_statement", "")
        domain = principle.get("domain", "")

        # Fact safety: asla fakt/year-specific values içerecek
        if _FACT_LIKE_PATTERN.search(strategy_stmt):
            return None  # Fact leakage -- ipucu REDDEDILIR

        # Sadece süreç ipucu: "Dönemi belirle, araştır, doğrula" gibi
        hint = (
            f"\n\n[PRINCIPLE STRATEGY GUIDANCE -- ilke aktif, sadece süreç önerisi]"
            f"\n{strategy_stmt}"
            "\nBu ipucu yalnız bir SÜREÇ önerisidir: oran/tutar/yıl/mevzuat "
            "sonuçunu TAŞITMAZ. Yukarıdaki deneyimlerle destekleniyorsa kullan."
        )
        return hint

    def _maybe_augment_with_experience(self, prompt):
        advice = self._current_advice
        if advice is None or not advice.applied:
            return prompt
        self.last_trace.strategy_consumed = True
        self.last_trace.strategy_effect = "grounded_prompt_guidance"
        return prompt + StrategyAdvisor.render_hint(advice)

    # --- 4. yerel hafıza -----------------------------------------------------------------
    def _grounded_answer(self, question, domain, evidence):
        if (self._current_advice is not None and self._current_advice.action == "extractive_first"
                and not (self._last_reasoning_context and self._last_reasoning_context.event_type)):
            # Reuse a validated PROCESS; the text still comes from this question's evidence.
            excerpt = self.brain.extractive_answer(question, evidence, strict=False)
            if excerpt:
                self.last_trace.strategy_consumed = True
                self.last_trace.strategy_effect = "extractive_instead_of_model"
                return None  # caller uses its normal evidence-only extractive branch
        context = self._last_reasoning_context
        if context is not None and context.event_type and context.account_effects:
            # Source-backed structured conclusion in the existing grounded answer path.
            # Render accounting effects, never trace/strategy/internal metadata.
            parts = []
            alternatives = []
            for effect in context.account_effects:
                account = effect["account"] + " " + effect["name"]
                direction = {"debit": "borç", "credit": "alacak"}[effect["direction"]]
                if effect.get("alternative_group"):
                    alternatives.append((account, direction))
                    continue
                prefix = "İndirime konu KDV varsa, " if effect.get("conditional") == "kdv" else ""
                parts.append(f"{prefix}{account} hesabına {direction} yazılır.")
            if alternatives:
                names = " veya ".join(a for a, _ in alternatives)
                parts.append(f"Peşin ödemenin yapıldığı hesaba göre {names} hesabına {alternatives[0][1]} yazılır. Kullanılacak hesap ödeme yöntemine bağlıdır.")
            if context.missing_information:
                parts.append("Netleştirilmesi gereken bilgi: " + "; ".join(context.missing_information) + ".")
            sources = list(evidence)
            for pid in context.relevant_principle_ids:
                try:
                    principle = self._principle_retriever.registry.get(pid)
                except Exception:
                    principle = None
                if principle and principle.get("description"):
                    from accounting.retriever import Evidence
                    parts.append(principle["description"])
                    sources.append(Evidence("course", principle["source"], principle["description"], curated=True))
            return "\n".join(parts) + "\n\n" + self.brain.sources_block(sources)
        prompt = self.brain.build_prompt(question, domain, evidence)
        prompt = self._maybe_augment_with_principle(question, domain, prompt)
        prompt = self._maybe_augment_with_experience(prompt)
        try:
            answer = self._ask_provider(prompt)
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

        madde 28-31: `research_engine_enabled` + `search_provider` ikisi de VARSA önce
        Research Engine denenir (`_research_engine_once`); yalnızca SUPPORTED (madde 27'nin
        en yüksek güveni, birden fazla/resmî bağımsız kaynakla uzlaşı sağlanmış) bir sonuç
        ürettiğinde onu kullanır. Research Engine hiçbir şey bulamazsa (None döner -- PARTIAL/
        CONFLICTED/INSUFFICIENT/SEARCH_DEGRADED/SEARCH_UNAVAILABLE dahil TÜM diğer durumlarda,
        madde 30) Hermes (`accounting_agent.ask`) HİÇ DEĞİŞMEDEN, HER ZAMANKİ GİBİ fallback
        olarak çalışır -- bu satırın kendisi, bayrak kapalıyken (varsayılan) `result=None` ile
        başlayıp doğrudan Hermes'e düşmesi anlamında MEVCUT davranışı BİREBİR korur.

        Başarılı sonuç, kendi kendini geliştiren beyin tarafından bilgi kartı olarak hafızaya işlenir
        (`_remember_research`); bir dahaki sefere aynı/benzer soru için araştırmaya gerek kalmayabilir.
        """
        if self._research_cache[0] != question:
            if self.last_trace is not None:
                self.last_trace.research_needed = True
            result = self._research_engine_once(question)
            self._last_research_via = "engine" if result is not None else None
            if result is None:
                if self.strict_fact_safety and self.needs_current_research(question):
                    result = "Kaizen: Yerel model doğrulanmış güncel kaynak bulamadı; değer uydurmayacağım."
                    self._research_cache = (question, result)
                    return result
                result = self.accounting_agent.ask(question)
                self._last_research_via = "hermes"
                if self.last_trace is not None and self._research_engine_attempted():
                    self.last_trace.fallback_used = True  # Engine denendi, Hermes devraldı
            if not self._research_failed(result):
                self._remember_research(question, result)
            self._research_cache = (question, result)
        return self._research_cache[1]

    def _research_engine_once(self, question):
        """madde 28-31: Research Engine'i bir kez dener, YALNIZ SUPPORTED (madde 27) bir
        sonuç varsa metne çevirip döner; aksi halde None döner (çağıran, Hermes'e düşer).
        Bayrak kapalıysa VEYA `search_provider` hiç verilmemişse (varsayılan durum) HİÇ
        çalışmaz -- iki bağımsız güvenlik kapısı (Learning Brain'in flag+retriever ikilisiyle
        AYNI desen). `run_research` kendi içinde zaten hiçbir zaman raise etmez (madde 26)
        ama burada YİNE DE geniş bir try/except var -- bu SAVUNMA KATMANI, bilinen bir
        hatayı ÖRTBAS etmek için değil, Research Engine'in Kaizen'in ana cevap zincirini
        ASLA çökertmemesi gereken bir entegrasyon noktası olduğu için (madde 26)."""
        if not self.research_engine_enabled or self._search_provider is None:
            return None
        if self._research_fetcher is None:
            self._research_fetcher = get_adapter()
        if hasattr(self._research_fetcher, "reset_metrics"):
            self._research_fetcher.reset_metrics()
        try:
            result = run_research(question, self._search_provider, self._research_fetcher)
        except Exception:
            self._note_research_attempt_failed()
            return None
        if self.last_trace is not None:
            for key, value in getattr(self._research_fetcher, "metrics", {}).items():
                if key.startswith("scrapling_") and hasattr(self.last_trace, key):
                    setattr(self.last_trace, key, value)
        self._record_research_meta(result)
        # SINIR (kodda açık): burada dönen metin en fazla PENDING kart/SUPPORTED-research
        # güvenidir. Research SUPPORTED, FactRegistry VERIFIED DEĞİLDİR -- hiçbir yol
        # araştırma sonucunu parametre defterine (accounting/facts.py) yazmaz.
        return _format_research_result(result)

    def _research_engine_attempted(self):
        return bool(self.research_engine_enabled and self._search_provider is not None)

    def _note_research_attempt_failed(self):
        """Research Engine denendi ama beklenmedik istisna verdi: gerçek durum 'çalışmadı'."""
        if self.last_trace is not None:
            self.last_trace.search_provider = type(self._search_provider).__name__

    def _record_research_meta(self, result):
        """ResearchResult -> yalnız SAYAÇ/DURUM (research/summary.py): trace + öğrenme katmanı."""
        try:
            meta = summarize_research(result, type(self._search_provider).__name__)
        except Exception:
            return
        self._last_research_meta = meta
        trace = self.last_trace
        if trace is not None:
            trace.research_status = meta["status"]
            trace.search_provider = meta["search_provider"]
            trace.search_health = meta["search_health"]
            trace.query_count = meta["query_count"]
            trace.result_count = meta["result_count"]
            trace.fetched_count = meta["fetched_count"]
            trace.evidence_count = meta["evidence_count"]
            trace.official_evidence_count = meta["official_evidence_count"]
            trace.consensus_status = meta["consensus_status"]
            trace.conflict_count = meta["conflict_count"]

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
        self.last_trace.retrieval_source = "card"
        self.last_trace.refusal_reason = None  # kart bulundu -- bu bir refuse değil
        # Bu kart için kapatılmamış bir çelişki kaydı varsa (facts ile veya iki araştırma turu
        # arasında), güven etiketi PENDING/VERIFIED değil CONFLICTED olmalı -- "embedding ile
        # benzer bulundu" ile "doğru" birbirine karıştırılmasın (iş emri madde 8, GÜVEN MODELİ).
        if any(row["card_id"] == card["id"] for row in self.brain.cards.contradictions()):
            self.last_trace.confidence = CONFLICTED
        note = "" if card["status"] == "confirmed" else (
            "NOT: Bu bilgi tek bir araştırma turundan öğrenildi, henüz ikinci bağımsız doğrulama görmedi "
            "(mali müşavir 'onayla: <soru>' ile onaylayabilir).\n\n")
        text = f"{note}Kaizen (önceki araştırmadan öğrenilmiş bilgi):\n{card['answer']}\n\nKAYNAK: {card['source_label']}"
        return text, False

    @staticmethod
    def _evidence_top_score(question, evidence):
        """Retriever.coverage() -- sorudaki anlamlı kelimelerin en iyi kanıt parçasında kaçının
        geçtiği (0..1) -- trace'teki retrieval_score için mevcut iç metriği aynen açığa çıkarır;
        yeni bir puanlama algoritması İCAT ETMEZ."""
        if not evidence:
            return None
        from accounting.retriever import Retriever
        return round(Retriever.coverage(question, evidence[0].text, ignore_frame=True), 3)

    def _from_memory(self, question, domain, current):
        """Yerel hafızadan cevap. Güncel bir soruda toplanmış site kanıtı yoksa önce araştırma denenir."""
        if self.strict_fact_safety and current:
            self.last_route = "research"
            self.last_trace.used_research = True
            result = self._research_once(question)
            if not self._research_failed(result):
                self.last_trace.retrieval_source = "research"
                return result, False
            self.last_trace.refusal_reason = REFUSAL_CURRENT_FACT_MISSING
            return None, False
        context = self._last_reasoning_context
        if context is not None and context.event_type and context.account_effects:
            from accounting.retriever import Evidence
            evidence = [Evidence("course", r["source_path"] + " — " + r["section"] + " — " + (r.get("locator") or ""),
                                 r["text"], curated=True) for r in context.source_records]
            self.last_trace.used_memory = True
            self.last_trace.retrieval_source = "knowledge_template"
            self.last_route = "memory_grounded"
            return self._grounded_answer(question, domain, evidence), False
        started = time.perf_counter()
        try:
            evidence = self.brain.gather_evidence(question, domain, current)
        except Exception as exc:
            evidence = []
            self.last_trace.fallback_reason = "retrieval:" + type(exc).__name__
        self.last_trace.latency_breakdown["retrieval_ms"] = round((time.perf_counter() - started) * 1000, 3)
        metrics = getattr(self.brain.retriever, "last_metrics", {})
        for key in ("retrieval_mode", "lexical_candidate_count", "semantic_used", "cache_hits", "cache_misses", "embedding_attempted", "embedding_success", "semantic_ms", "lexical_order", "semantic_order"):
            if key in metrics:
                setattr(self.last_trace, key, metrics[key])
        if metrics.get("fallback_reason"):
            self.last_trace.fallback_reason = "embedding:" + metrics["fallback_reason"]
        self.last_trace.used_memory = True
        if evidence:
            self.last_trace.retrieval_score = self._evidence_top_score(question, evidence)
        stale_note = ""
        if current and domain == "accounting" and not any(e.kind == "site" for e in evidence):
            self.last_route = "research"
            self.last_trace.used_research = True
            researched = self._research_once(question)
            if not self._research_failed(researched):
                self.last_trace.retrieval_source = "research"
                return researched, False
            if not evidence:
                self.last_trace.refusal_reason = REFUSAL_CURRENT_FACT_MISSING
                return self._card_fallback(question, domain)
            stale_note = ("NOT: Güncel kaynak doğrulanamadı; aşağıdaki bilgi ders notlarından geliyor "
                          "ve güncel olmayabilir.\n\n")
        if not evidence:
            self.last_trace.refusal_reason = REFUSAL_RETRIEVAL_NO_MATCH
            return self._card_fallback(question, domain)
        answer = self._grounded_answer(question, domain, evidence)
        if answer == "NOT_FOUND":
            self.last_trace.refusal_reason = REFUSAL_RETRIEVAL_THRESHOLD_FAILED
            fallback, _ = self._card_fallback(question, domain)
            return (fallback, False) if fallback else (None, True)
        if answer is None:  # model yok: kanıttan düz cevap (soruyla yeterince örtüşmüyorsa vermez)
            extractive = self.brain.extractive_answer(question, evidence, strict=current)
            if extractive is None:
                self.last_trace.refusal_reason = REFUSAL_RETRIEVAL_THRESHOLD_FAILED
                return self._card_fallback(question, domain)
            self.last_route = "memory_extractive"
            self.last_trace.retrieval_source = "ders_veya_site"
            return stale_note + extractive, False
        self.last_route = "memory_grounded"
        self.last_trace.retrieval_source = "ders_veya_site"
        return stale_note + answer, False

    # --- ana giriş -------------------------------------------------------------------------
    def answer(self, message):
        """Answer, record trace, and update the active learning systems."""
        started = time.perf_counter()
        # --- Document & Office Engine (LOCAL_ONLY): mesajda VAR OLAN yerel dosya yolu +
        # islem fiili varsa, belge zinciri tum diger yollardan ONCE deterministic olarak
        # devreye girer. Belge icerigi modele/uzak uca GITMEZ; bu rota provider HIC
        # cagirmaz. Dosya yolu yoksa ya da niyet belge islemi degilse None doner ve
        # normal akis BITIRILMEDEN surer (office_missing dahil mevcut redler korunur).
        from documents.router import route_document_request, format_document_answer
        try:
            doc_result = route_document_request(message)
        except Exception as exc:
            doc_result = None
            self.last_trace = KaizenTrace()
            self.last_trace.fallback_reason = "document_engine:" + type(exc).__name__
        if doc_result is not None:
            self.last_route = "document_engine"
            self.last_trace = KaizenTrace(
                intent="office", route="document_engine", decision="answer_document_engine",
                retrieval_source="local_document", confidence=ROUTE_CONFIDENCE["document_engine"])
            self.last_trace.document_validation = {"operation_ok": doc_result.ok,
                                                    "status": doc_result.status,
                                                    "output_path": str(doc_result.output_path or ""),
                                                    "provenance": list(doc_result.provenance)}
            return format_document_answer(doc_result)
        observed = getattr(self.provider, "provider", None)
        calls_before = getattr(observed, "calls", None)
        elapsed_before = getattr(observed, "elapsed_ms", 0.0)
        answer = self._answer_core(message)
        self._finalize_trace()
        core_finished = time.perf_counter()
        self.last_trace.latency_breakdown["answer_core_ms"] = round((core_finished - started) * 1000, 3)
        if calls_before is not None and hasattr(observed, "elapsed_ms"):
            self.last_trace.model_calls = observed.calls - calls_before
            self.last_trace.used_model = bool(self.last_trace.model_calls)
            self.last_trace.latency_breakdown["model_ms"] = round(observed.elapsed_ms - elapsed_before, 3)
        exact_only = self.strict_fact_safety and self.last_route in {"arithmetic", "calculator", "chart", "journal", "facts", "accounting_clarification", "accounting_invalid"}
        if answer and not exact_only and self.last_route not in ("empty", "not_found_offline", "office_missing"):
            # KAIZEN BUYUK IS EMRI #21, Faz 21-24: Brain v2 - After successful answer,
            # trigger principle discovery pipeline (aracli, feature-flag'li).
            if self.principle_discovery_enabled and self._principle_discovery is not None:
                try:
                    discovered = self._principle_discovery.discover_principle()
                    if discovered:
                        # New principle discovered and validated
                        self.last_trace.principle_discovered = discovered.get("principle_id", None)
                        self.last_trace.principle_discovery_status = discovered.get("status", None)
                        # Store for trace visibility
                        self.last_trace.principle_confidence = discovered.get("confidence", None)
                        self.last_trace.principle_support_count = discovered.get("independent_support_count", 0)
                except Exception as exc:
                    # Discovery hatası cevabı etkilemez, loglanir
                    if self.last_trace is not None:
                        self.last_trace.fallback_reason = "discovery:" + type(exc).__name__
        self._reflect(message, answer)
        if self.last_trace is not None:
            self.last_trace.elapsed_ms = int(round((time.perf_counter() - started) * 1000))
            self.last_trace.verification_result = self.last_trace.confidence
            if self.last_route in {"arithmetic", "calculator", "chart", "journal"}:
                self.last_trace.deterministic_tool = self.last_route
            if self._runtime_learning is not None:
                try:
                    learned = self._runtime_learning.observe(message, self.last_trace, answer, self._last_research_meta)
                    for key, value in learned.items():
                        if key not in {"strategy", "learned_principle_id"} or getattr(self.last_trace, key) is None:
                            setattr(self.last_trace, key, value)
                    self.last_trace.reflection_written = True
                except Exception as exc:
                    self.last_trace.fallback_reason = "learning:" + type(exc).__name__
            self.last_trace.latency_breakdown["learning_ms"] = round((time.perf_counter() - core_finished) * 1000, 3)
            self.last_trace.elapsed_ms = round((time.perf_counter() - started) * 1000)
        return answer

    # --- Accountant Phase 2: document <-> journal reconciliation ------------------------
    def reconcile_document(self, document, journal_entry):
        """Explicit production entry point for document<->journal reconciliation.

        This is NOT part of the natural-language `answer()`/`cevap_ver` chain and is
        NEVER called from it. Ordinary Phase-1 accounting questions (ör. "Kasadan
        bankaya 5.000 TL yatırdım.") go exclusively through `answer()` and never reach
        this method -- reconciliation only activates when a caller explicitly supplies
        a `NormalizedDocument` (`accounting.document_reconciliation.NormalizedDocument`)
        and an existing journal entry (a real `accounting.journal.JournalEntry` or its
        `.to_dict()` shape) to compare it against. No parallel journal engine is used:
        `reconcile_document_entry` reads the same Phase-1 account codes/labels as-is.

        Returns the KAIZEN production response text; the structured outcome is also
        recorded on `self.last_trace` (document_validation/reconciliation_status/
        discrepancies/missing_information), same observability pattern as every other
        route in this file.
        """
        self.last_route = "document_reconciliation"
        self.last_trace = KaizenTrace()
        result = reconcile_document_entry(document, journal_entry, self.last_trace)
        self.last_trace.route = self.last_route
        self.last_trace.decision = "answer_document_reconciliation"
        self.last_trace.confidence = ROUTE_CONFIDENCE.get(self.last_route, UNKNOWN)
        self.last_trace.deterministic_tool = self.last_route
        self.last_trace.deterministic_tool_used = True

        if result.status == result.MATCH:
            return "SONUÇ: MATCH — Belge ve yevmiye kaydı tutarlı."

        lines = [f"SONUÇ: {result.status}"]
        if result.discrepancies:
            lines.append("UYUŞMAZLIKLAR:")
            lines.extend(f"  - {d}" for d in result.discrepancies)
        if result.missing_information:
            lines.append("EKSİK BİLGİ:")
            lines.extend(f"  - {m}" for m in result.missing_information)
        return "\n".join(lines)

    # --- Accountant Phase 4: kismi / taksitli alacak tahsilati --------------------------
    def reconcile_collection(self, document, journal_entry, outstanding_receivable=None):
        """Explicit production entry point for receivable-collection reconciliation
        (kismi/taksitli/tam tahsilat). Faz-2/3 `reconcile_document` deseninin aynisi:
        dogal dil `answer()`/`cevap_ver` zincirinin DISINDA, ayri ve acik bir giris
        noktasi -- olağan Faz-1 soruları bu kodu hic cagirmaz. Yeni bir muhasebe
        motoru kurulmadi: `accounting.receivable_collection.reconcile_receivable_collection`
        icinceden mevcut Faz-2/3 `reconcile_document_entry` denetimini calistirir ve
        ustune yalnizca acik-alacak pozisyonu aritmetigi ekler (kalan alacak,
        kismi/tam ayrimi, fazla tahsilat reddi). Tahsilatta 600/391 yeniden
        olusturulmasi mevcut Faz-3 denetimiyle reddedilir; burada tekrarlanmaz.

        Donus: KAIZEN uretim cevap metni; yapilandirilmis sonuc `self.last_trace`
        uzerinde de kayitlidir (ustteki Faz-2/3 alanlari + `collection_details`).
        """
        self.last_route = "receivable_collection"
        self.last_trace = KaizenTrace()
        result = reconcile_receivable_collection(
            document, journal_entry, outstanding_receivable, self.last_trace)
        self.last_trace.route = self.last_route
        self.last_trace.decision = "answer_receivable_collection"
        self.last_trace.confidence = ROUTE_CONFIDENCE.get(self.last_route, UNKNOWN)
        self.last_trace.deterministic_tool = self.last_route
        self.last_trace.deterministic_tool_used = True

        if result.status == result.MATCH:
            if result.collection_type == "full":
                return "SONUÇ: MATCH — Tahsilat açık alacakla tutarlı; alacak tamamen kapandı."
            return (f"SONUÇ: MATCH — Kısmi tahsilat açık alacakla tutarlı; "
                    f"kalan alacak {result.remaining_receivable} TL.")

        lines = [f"SONUÇ: {result.status}"]
        if result.discrepancies:
            lines.append("UYUŞMAZLIKLAR:")
            lines.extend(f"  - {d}" for d in result.discrepancies)
        if result.missing_information:
            lines.append("EKSİK BİLGİ:")
            lines.extend(f"  - {m}" for m in result.missing_information)
        return "\n".join(lines)

    def _ask_provider(self, message):
        actual = getattr(self.provider, "provider", self.provider)
        if getattr(actual, "is_offline", False):
            self.last_trace.used_model = bool(self.last_trace.model_calls)
            from core.ai.offline_provider import OFFLINE_MESSAGE
            return OFFLINE_MESSAGE
        started = time.perf_counter()
        self.last_trace.used_model = True
        self.last_trace.model_calls += 1
        try:
            return self.provider.ask(message)
        except Exception as exc:
            self.last_trace.fallback_reason = "model:" + type(exc).__name__
            return "Kaizen: Yerel model kullanılamıyor (çevrimdışı mod)."
        finally:
            self.last_trace.latency_breakdown["model_ms"] = round((time.perf_counter() - started) * 1000, 3)

    # --- Learning Loop: cevap sonrası yapısal deneyim kaydı + kullanıcı geri bildirimi -------
    def _reflect(self, message, answer):
        """Cevap verildikten SONRA (kullanıcıya giden metni ETKİLEMEDEN) deneyimi kaydeder.
        Kaydedilen şey yalnız YAPI/META'dır (bkz. learning/reflection_lifecycle.py); ham cevap,
        oran, tutar, yıl ASLA. Hata olursa cevap zinciri etkilenmez."""
        lifecycle = self._reflection_lifecycle
        trace = self.last_trace
        if lifecycle is None or trace is None:
            return
        try:
            lowered = message.casefold().lstrip()
            prefixed = lowered.startswith("muhasebe:") or lowered.startswith("matematik:")
            question = message.split(":", 1)[1].strip() if ":" in message and prefixed else message.strip()
            info = lifecycle.record_answer(
                question, trace.intent or "general", trace, answer_text=answer,
                research_meta=self._last_research_meta, needs_current=trace.needs_current_data,
                reasoning_context=self._last_reasoning_context,
            )
        except Exception:
            trace.reflection_written = False
            return
        if info is None:
            return  # deterministik/otoriter rota veya boş: kaydedilecek bir çözüm stratejisi yok
        trace.reflection_written = True
        trace.experience_candidate = bool(info["reusable_candidate"])

    def record_feedback(self, question, positive):
        """`onayla:` (positive=True) / `düzelt:` (positive=False) sonucunu ilgili deneyime bağlar.
        Mevcut kart onayı / düzeltme mekanizmasından BAĞIMSIZ ve ONLARI DEĞİŞTİRMEDEN çalışır;
        hata olursa None döner. Kullanıcının verdiği rakam/mevzuat burada HİÇBİR YERE yazılmaz
        (yalnız sayaç ve bayrak değişir) -- FACT doğrulama politikası (FactRegistry/kartlar)
        ayrı ve aynen kalır."""
        lifecycle = self._reflection_lifecycle
        runtime_effect = None
        if self._runtime_learning is not None:
            try:
                runtime_effect = self._runtime_learning.feedback(question, positive)
            except Exception:
                pass
        if lifecycle is None:
            return runtime_effect
        try:
            effect = lifecycle.apply_feedback(question, positive)
        except Exception:
            return runtime_effect
        self.last_feedback_effect = effect
        if runtime_effect and runtime_effect.get("applied"):
            effect = runtime_effect
            self.last_feedback_effect = effect
        if self.last_trace is not None and effect.get("applied"):
            self.last_trace.user_feedback_effect = (
                f"{effect['feedback']}:reusable={effect['reusable']}" if effect.get("applied") else None
            )
        return effect

    def _decision_for_route(self, route):
        """route -> insan-okunur karar etiketi. Yalnız GERÇEKTEN olanı söyler (research_via
        yalnız araştırma yolu çalıştıysa dolu)."""
        if route in ("arithmetic", "journal", "calculator", "chart"):
            return "answer_exact"
        if route == "accounting_clarification":
            return "ask_missing_facts"
        if route == "accounting_invalid":
            return "reject_invalid_entry"
        if route == "facts":
            return "answer_facts"
        if route == "correction":
            return "answer_correction"
        if route == "research":
            return "answer_research_engine" if self._last_research_via == "engine" else "answer_research_hermes"
        if route in ("memory_grounded", "memory_extractive"):
            return "answer_memory"
        if route in ("memory_card_confirmed", "memory_card_pending"):
            return "answer_card"
        if route == "provider":
            return "answer_model"
        if route in ("not_found_offline", "office_missing", "empty"):
            return "refuse"
        return None

    def _finalize_trace(self):
        """`_answer_core` bitince (tek bir yerde, `answer()` sarmalayıcısından) trace'i
        tamamlar: route'u self.last_route ile eşitler, güven etiketini ROUTE_CONFIDENCE
        eşlemesinden türetir. Kullanıcıya giden METİN cevabı bu fonksiyondan hiç etkilenmez --
        yalnız self.last_trace güncellenir."""
        if self.last_trace is None:
            return
        self.last_trace.route = self.last_route
        self.last_trace.decision = self._decision_for_route(self.last_route)
        # CONFLICTED, _card_fallback tarafından zaten (daha özgül bir bilgiyle: bu KARTIN
        # açık bir çelişkisi olduğu) önceden set edilmiş olabilir -- route'a göre kaba
        # varsayılanla EZİLMEMELİ.
        if self.last_trace.confidence != CONFLICTED:
            self.last_trace.confidence = ROUTE_CONFIDENCE.get(self.last_route, UNKNOWN)

    def _answer_core(self, message):
        self.last_route = None
        self._research_cache = (None, None)
        self.last_trace = KaizenTrace()
        self._current_advice = None
        self._last_research_meta = None
        self._last_research_via = None
        # KAIZEN BUYUK IS EMRI #21, Faz 24-26: Brain v2 - Principle retrieval for
        # strategy guidance. AKTIF illeri soru yapısına göre retrieve et.
        retrieved_principle = None
        if self.principle_discovery_enabled and self._principle_discovery is not None:
            try:
                retrieved_principle = self._principle_discovery.retrieve_principle_for_question(message)
            except Exception:
                retrieved_principle = None
        if retrieved_principle is not None:
            self.last_trace.retrieved_principle_id = retrieved_principle.get("principle_id") if isinstance(retrieved_principle, dict) else retrieved_principle.principle_id
            self.last_trace.retrieved_principle_confidence = retrieved_principle.get("confidence") if isinstance(retrieved_principle, dict) else retrieved_principle.confidence
            self.last_trace.principle_selected_for_strategy = True
        else:
            self.last_trace.retrieved_principle_id = None
            self.last_trace.retrieved_principle_confidence = None
            self.last_trace.principle_selected_for_strategy = False
        lowered = message.casefold().lstrip()
        prefixed = lowered.startswith("muhasebe:") or lowered.startswith("matematik:")
        question = message.split(":", 1)[1].strip() if ":" in message and prefixed else message.strip()
        domain = self.classify(message)
        previous_context = self._last_reasoning_context
        if self._reasoning_engine.purchase_candidate(question, previous_context):
            domain = "accounting"
        self._last_reasoning_context = None
        self.last_trace.intent = domain

        # Accountant Reasoning Core v1: accounting intent algılandığında önce
        # structured reasoning context oluştur (kullanıcıya GÖSTERİLMEZ, internal).
        if domain == "accounting" and self._reasoning_engine is not None:
            try:
                current = self.needs_current_research(question)
                reasoning_ctx = self._reasoning_engine.build_context(question, domain, current, previous=previous_context)
                self._last_reasoning_context = reasoning_ctx
                self.last_trace.accounting_reasoning_used = True
                self.last_trace.problem_type = reasoning_ctx.problem_type
                self.last_trace.concept_ids = reasoning_ctx.relevant_concepts
                self.last_trace.principle_ids = reasoning_ctx.relevant_principle_ids
                self.last_trace.deterministic_tool_used = reasoning_ctx.deterministic_tool_needed
                self.last_trace.current_fact_needed = reasoning_ctx.current_fact_needed
                self.last_trace.knowledge_source_types = reasoning_ctx.knowledge_sources
                self.last_trace.accounting_reasoning_context = reasoning_ctx.to_dict()
                self.last_trace.principle_retrieval_status = reasoning_ctx.principle_retrieval_status
            except Exception:
                self._last_reasoning_context = None
                self.last_trace.accounting_reasoning_used = False
        else:
            self._last_reasoning_context = None
            self.last_trace.accounting_reasoning_used = False

        if not question:
            self.last_route = "empty"
            self.last_trace.refusal_reason = REFUSAL_EMPTY_QUESTION
            return "Kaizen: Muhasebe sorusu bos olamaz." if lowered.startswith("muhasebe") else "Kaizen: Soru bos olamaz."

        corrected = self._correction(question)
        if corrected and not self.strict_fact_safety:
            self.last_route = "correction"
            return corrected

        arithmetic = self._arithmetic(question)
        if arithmetic:
            self.last_route = "arithmetic"
            self.last_trace.retrieval_source = "exact_tool"
            return arithmetic

        exact = self._exact_tools(question)
        if exact and exact.startswith("Kaizen: Tutarı belirtmediniz") and self.last_route == "journal":
            # Tutarsız kayıt sorusu: önce kavramsal cevabı (öğretilmiş şablon/ders notu) dene, sonra tutar iste
            explained, _ = self._from_memory(question, "accounting", False)
            if explained and self.last_route.startswith("memory"):
                return explained + "\n\nNOT: Tutarı (ve varsa KDV oranını) yazarsan kaydı rakamlarla, kuruşu kuruşuna çıkarırım."
            self.last_route = "journal"
        if exact:
            self.last_trace.retrieval_source = self.last_trace.retrieval_source or "exact_tool"
            return exact

        current = self.needs_current_research(question)
        self.last_trace.needs_current_data = current
        fact = self.brain.verified_fact_answer(question, strict=self.strict_fact_safety)
        self.last_trace.used_facts = True
        if fact:
            self.last_route = "facts"
            self.last_trace.retrieval_source = "facts"
            return fact

        if corrected and self.strict_fact_safety and not current:
            self.last_route = "correction"
            return corrected

        if self.strict_fact_safety and current and domain in ("general", "accounting"):
            self.last_trace.used_research = True
            result = self._research_once(question)
            if not self._research_failed(result):
                self.last_route = "research"
                return result
            self.last_route = "not_found_offline"
            self.last_trace.refusal_reason = REFUSAL_CURRENT_FACT_MISSING
            return "Kaizen: Güncel bilgiyi kaynaklarıyla doğrulayamadım; cevap uydurmayacağım."

        # Learning Loop (öncelik 6): deterministik + FactRegistry GEÇİLDİ; şimdi -- ve ancak şimdi --
        # onaylı deneyimden süreç önerisi alınabilir. Yıla bağlı güncel parametre yapısı için
        # araştırma tetiklemeyi öne çekebilir; cevabın KAYNAĞI olamaz.
        if self._advise_strategy(question, domain, current):
            self.last_trace.strategy_consumed = True
            self.last_trace.strategy_effect = "research_before_answer"
            current = True
            self.last_trace.needs_current_data = True

        if domain == "general":
            self.last_route = "provider"
            self.last_trace.used_model = True
            reply = self._ask_provider(message)
            if is_failure(reply):  # model kapalı: yine de yerel hafızada ilgili kayıt var mı?
                remembered, _ = self._from_memory(question, "general", current)
                if not remembered:
                    self.last_trace.refusal_reason = REFUSAL_MODEL_UNAVAILABLE
                return remembered or reply
            return reply

        memory_answer, model_said_missing = self._from_memory(question, domain, current)
        if memory_answer:
            return memory_answer

        if domain == "accounting" and current:
            self.last_route = "research"
            self.last_trace.used_research = True
            researched = self._research_once(question)
            if is_failure(researched):
                self.last_route = "not_found_offline"
                self.last_trace.refusal_reason = REFUSAL_RESEARCH_FAILED
                return ("Kaizen: Bu soruyu yerel hafızamda bulamadım ve araştırma modeli şu an kullanılamıyor. "
                    "'güncelle' komutuyla güvenilir siteleri tarayıp hafızamı güncelleyebilirsin; "
                    "cevabı uydurmayacağım." + self._research_status_sentence())
            self.last_trace.retrieval_source = "research"
            return researched
        if domain == "office":
            self.last_route = "office_missing"
            self.last_trace.refusal_reason = self.last_trace.refusal_reason or REFUSAL_RETRIEVAL_NO_MATCH
            return ("Kaizen: Bu ofis konusu için yerel hafızada doğrulanmış bilgi yok. "
                "İşlem veya formül uydurmayacağım; kaynak eklendiğinde öğrenirim.")
        if domain == "accounting" and self.strict_fact_safety:
            # Grounded synthesis already had its chance in _from_memory. Retrying
            # with the bare question would discard the accounting truth boundary.
            if self.general_accounting_model_answer and not current:
                # Cevap-verme düzeltmesi (2026-10-03, config: runtime.general_accounting_model_answer):
                # güncel parametre İSTEMEYEN (oran/limit/yıl yok) kavramsal bir muhasebe sorusunda
                # kaynak bulunamadıysa kullanıcı cevapsız bırakılmaz -- model genel bilgiyle cevaplar,
                # ama AÇIKÇA "doğrulanmış kaynak yok" notuyla (güven UNKNOWN kalır).
                reply = self._ask_provider(message)
                if not is_failure(reply) and not str(reply).startswith("Kaizen:") and not says_not_found(str(reply)):
                    self.last_route = "provider"
                    self.last_trace.refusal_reason = None
                    return ("NOT: Bu cevap yerel kaynaklarda doğrulanmış bir kayda dayanmıyor; genel muhasebe "
                            "bilgisidir. Tutar, oran veya mevzuat için kaynağı kontrol edin.\n\n" + str(reply).strip())
            self.last_route = "not_found_offline"
            self.last_trace.refusal_reason = self.last_trace.refusal_reason or REFUSAL_RETRIEVAL_NO_MATCH
            return "Kaizen: Bu muhasebe sorusunu mevcut kaynaklarla güvenilir biçimde cevaplayamadım; cevap uydurmayacağım."
        self.last_route = "provider"
        self.last_trace.used_model = True
        reply = self._ask_provider(message)
        if domain == "accounting" and is_failure(reply):
            self.last_route = "not_found_offline"
            self.last_trace.refusal_reason = REFUSAL_MODEL_UNAVAILABLE
        return reply

    def _research_status_sentence(self):
        """Research Engine GERÇEKTEN çalıştıysa, neden doğrulanamadığını dürüstçe söyler
        (yalnız gözlenen durum; çalışmadıysa '' -- olmayan olay uydurulmaz)."""
        meta = self._last_research_meta
        if not meta:
            return ""
        status = meta.get("status")
        if status in ("SEARCH_UNAVAILABLE", "SEARCH_DEGRADED"):
            return " (Araştırma: arama altyapısına şu an güvenilir biçimde ulaşılamadı.)"
        if status == "CONFLICTED":
            return " (Araştırma: kaynaklar birbiriyle çelişiyor; hangisinin doğru olduğunu doğrulayamadım.)"
        if status in ("INSUFFICIENT", "PARTIAL"):
            return " (Araştırma: bulunan kaynaklar soruyu, dönemiyle birlikte doğrulamaya yetmedi.)"
        return ""

