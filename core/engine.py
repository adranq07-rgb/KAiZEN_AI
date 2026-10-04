from pathlib import Path

from models.model_manager import ModelManager
from memory.memory_manager import MemoryManager
from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds
from memory.knowledge_cards import KnowledgeCardStore
from tools.tool_manager import ToolManager
from security.security_manager import SecurityManager
from core.logger import KaizenLogger
from config.config_manager import ConfigManager

from core.ai.provider_manager import ProviderManager
from core.ai.provider_factory import build_provider
from core.commands import CommandHandler
from accounting.accounting_agent import AccountingAgent
from accounting.site_store import SiteStore
from accounting.facts import FactRegistry
from core.kaizen_brain import KaizenBrain
from memory.principle_registry import PrincipleRegistry
from learning.principle_seed import load_principle_seeds
from learning.principle_retriever import PrincipleRetriever
from learning.reflection_lifecycle import ReflectionLifecycle
from learning.reflection_store import ReflectionStore
from learning.strategy_advisor import StrategyAdvisor
from search.searxng_provider import SearXNGProvider
from memory.brain_manager import BrainManager
from core.ai.embedding_client import OllamaEmbeddingClient
from core.ai.embedding_cache import EmbeddingCache
from core.ai.observed_provider import ObservedProvider
from learning.runtime_learning import RuntimeLearning
from memory.unavailable_store import UnavailableLearningStore


class KaizenEngine:
    def __init__(self, data_dir=None, log_dir=None, provider=None, config=None, experience_memory=None):
        """data_dir / log_dir / provider: yalnız testler için (bkz. tests/test_core.py).
        Üçü de None ise (normal kullanım -- main.py / desktop_app.py) davranış hiç değişmez:
        gerçek `data/`, `logs/` dizinleri ve config/Kaizen.json'dan seçilen gerçek provider
        kullanılır. Bir test `data_dir=<gecici klasör>` ve `provider=OfflineProvider()` verirse,
        Kaizen'in HİÇBİR kalıcı deposu (LearningStore, SiteStore, FactRegistry, KnowledgeCardStore,
        MemoryManager, AccountingAgent'ın LearningMemory'si, sınav öneri dosyası) ve hiçbir
        AI/ağ çağrısı gerçek kullanıcı ortamına dokunmaz."""
        self.config = config if config is not None else ConfigManager()
        self.component_failures = {}

        self.name = self.config.get("app", "name", "Kaizen AI")

        self.logger = KaizenLogger(log_dir=log_dir)
        self.model_manager = ModelManager()

        data_dir = Path(data_dir) if data_dir is not None else None

        self.memory_manager = MemoryManager(
            file_path=(data_dir / "kaizen_memory.json") if data_dir is not None else None
        )
        self.security_manager = SecurityManager()
        self.tool_manager = ToolManager(log_dir=log_dir)

        # Kaizen'in kendi hafizasi: ders notlari + ogretilmis bilgiler + toplanan siteler + parametre defteri
        self.learning_store = self._optional("knowledge", lambda: LearningStore(
            db_path=(data_dir / "kaizen_learning.sqlite3") if data_dir is not None else None
        ), UnavailableLearningStore())
        self.seed_report = self._optional("seed_loading", lambda: load_seeds(self.learning_store), {})
        self.site_store = self._optional("sites", lambda: SiteStore(
            db_path=(data_dir / "accounting_knowledge.sqlite3") if data_dir is not None else None
        ))
        self.facts = self._optional("facts", lambda: FactRegistry(self.site_store.db_path)) if self.site_store else None
        if self.facts is not None:
            self._optional("fact_refresh", lambda: self.facts.rebuild(self.site_store)
                if not self.facts.rows() and self.site_store.count(with_content=True) else None)

        # Kendi kendini geliştiren beyin: araştırmadan öğrenilen bilgi kartları (bkz. core/kaizen_brain.py)
        self.cards = self._optional("cards", lambda: KnowledgeCardStore(self.learning_store.db_path)) if self.learning_store.db_path else None

        # KAIZEN BUYUK GELISTIRME PAKETI #1, Faz C4 (madde 13): Learning Brain / Principle
        # Registry -- her zaman KURULUR (7 kuratorlu ilke yuklenir, data/kaizen_principles.sqlite3
        # -- test_dir verilirse gecici klasorde) ama KaizenBrain'e yalniz "gozlemlenebilir" bir
        # PrincipleRetriever olarak gecilir; onu GERCEKTEN cevaba karistirmak/karistirmamak TEK
        # BASINA config/Kaizen.json -> learning.learning_brain_enabled bayragina baglidir (varsayilan
        # False). Registry kurulumunun kendisi (madde 5: 7 ilke, provenance) mevcut FACT/hafiza
        # depolarina hic dokunmaz, ayri bir .sqlite3 dosyasidir.
        self.principle_registry = self._optional("principles", lambda: PrincipleRegistry(
            (data_dir / "kaizen_principles.sqlite3") if data_dir is not None else None
        ))
        self.principle_retriever = None
        if self.principle_registry is not None:
            self._optional("principle_seeds", lambda: load_principle_seeds(self.principle_registry))
            self.principle_retriever = PrincipleRetriever(self.principle_registry)

        # IS EMRI #2, Faz 28-31 (madde 28-31): Research Engine -- principle_retriever ile AYNI
        # desen: SearXNGProvider HER ZAMAN kurulur (kurulumun kendisi hicbir ag cagrisi yapmaz --
        # yalniz .search() cagrisinda SearXNG'ye baglanmaya calisir, o da research/engine.py::
        # run_research icinde zaten guvenle try/except'lenmis, madde 26) ama KaizenBrain'de
        # GERCEKTEN kullanilip kullanilmayacagi TEK BASINA config/Kaizen.json ->
        # research.research_engine_enabled bayragina baglidir (varsayilan False).
        self.search_provider = SearXNGProvider(base_url=self.config.get("research", "base_url", "http://127.0.0.1:8890"))

        # AI provider katmani: Hermes (gecici) -> yerel model -> cevrimdisi; config/Kaizen.json'dan secilir
        # `provider` verilirse (testlerde) build_provider() HİÇ çağrılmaz -- gerçek Hermes/Local
        # kurulumu (ağ/yerel sunucu bağlantısı) devreye girmez.
        self.provider_manager = ProviderManager()
        self.provider_observer = ObservedProvider(provider if provider is not None else build_provider(self.config, log_dir=log_dir))
        self.provider_manager.set_provider(self.provider_observer)
        # Learning Loop: Reflection/Experience yasam dongusu. ReflectionStore ayri bir .sqlite3
        # dosyasidir (data_dir verilirse gecici klasorde -- testler gercek data/'ya yazmaz). Bayraklar
        # kapaliysa hic KURULMAZ: eski davranis birebir korunur.
        self.reflection_store = None
        self.reflection_lifecycle = None
        self.strategy_advisor = None
        self.runtime_learning = None
        if self.config.experience_lifecycle_enabled() or self.config.experience_advice_enabled():
            try:
                self.reflection_store = ReflectionStore(
                    (data_dir / "kaizen_reflections.sqlite3") if data_dir is not None else None
                )
                if self.config.experience_lifecycle_enabled():
                    self.reflection_lifecycle = ReflectionLifecycle(self.reflection_store)
                if self.config.experience_advice_enabled():
                    self.strategy_advisor = StrategyAdvisor(self.reflection_store)
                if self.config.get("learning", "runtime_learning_enabled", False):
                    self.runtime_learning = RuntimeLearning(
                        (data_dir or Path(__file__).resolve().parent.parent / "data") / "kaizen_runtime_learning.sqlite3")
            except Exception as exc:
                self.component_failures["learning"] = type(exc).__name__
                self.logger.warning("Öğrenme deposu açılamadı; temel cevap yolları çalışmaya devam ediyor.")
        brain_manager = BrainManager(learning_store=self.learning_store, site_store=self.site_store,
            facts=self.facts, cards=self.cards, log_dir=log_dir,
            exam_candidates_path=(data_dir / "auto_exam_candidates.jsonl") if data_dir is not None else None,
            reflection_store=self.reflection_store,
            registry=self.principle_registry)
        if self.config.hybrid_retrieval_enabled():
            retriever = brain_manager.retriever
            try:
                retriever._embedding_client = OllamaEmbeddingClient(
                    base_url=self.config.get("retrieval", "base_url", "http://localhost:11434"),
                    model_name=self.config.get("retrieval", "model_name", "bge-m3"),
                    timeout=self.config.get("retrieval", "timeout", 90))
                retriever.hybrid_enabled = True
                retriever._embedding_cache = EmbeddingCache(
                    (data_dir / "kaizen_embedding_cache.sqlite3") if data_dir is not None else None)
            except Exception as exc:
                self.component_failures["embedding_cache"] = type(exc).__name__
        self.accounting_agent = AccountingAgent(
            self.provider_manager.provider,
            learning_memory_path=(data_dir / "accounting_learning.json") if data_dir is not None else None,
        )
        self.brain = KaizenBrain(
            self.provider_manager,
            self.accounting_agent,
            learning_store=self.learning_store,
            site_store=self.site_store,
            facts=self.facts,
            cards=self.cards,
            exam_candidates_path=(data_dir / "auto_exam_candidates.jsonl") if data_dir is not None else None,
            log_dir=log_dir,
            principle_retriever=self.principle_retriever,
            learning_brain_enabled=self.config.learning_brain_enabled(),
            search_provider=self.search_provider,
            research_engine_enabled=self.config.research_engine_enabled(),
            reflection_lifecycle=self.reflection_lifecycle,
            strategy_advisor=self.strategy_advisor,
            runtime_learning=self.runtime_learning,
            brain_manager=brain_manager,
            strict_fact_safety=True,
            general_accounting_model_answer=self.config.get("runtime", "general_accounting_model_answer", False),
            principle_discovery_enabled=self.config.get("learning", "principle_discovery_enabled", False),
            principle_discovery_min_support=self.config.get("learning", "principle_discovery_min_support", 3),
        )
        self.commands = CommandHandler(self)
        self._register_tools()

        self.logger.info(
            f"Kaizen Engine baslatildi. "
            f"Local First={self.config.local_first()} | "
            f"Cloud Allowed={self.config.cloud_allowed()} | "
            f"Learning Brain Enabled={self.config.learning_brain_enabled()} | "
            f"Research Engine Enabled={self.config.research_engine_enabled()}"
        )

    def _register_tools(self):
        from tools.subsystem_tools import register
        register(self.tool_manager)
        from tools.office_tools import OFFICE_TOOLS
        for name, function in OFFICE_TOOLS.items():
            self.tool_manager.register_tool(name, function)

    def _optional(self, name, factory, fallback=None):
        try:
            return factory()
        except Exception as exc:
            self.component_failures[name] = type(exc).__name__
            self.logger.warning(f"{name} kullanılamıyor; diğer cevap yolları açık.")
            return fallback

    def shutdown(self, timeout=5.0):
        return self.brain.brain.shutdown(timeout=timeout)

    def cevap_ver(self, mesaj):
        if not mesaj.strip():
            self.logger.warning("Bos mesaj alindi.")
            return f"{self.name}: Bos mesaj gonderdin."

        command_answer = self.commands.handle(mesaj)
        if command_answer is not None:
            return command_answer

        return self.brain.answer(mesaj)

    def reconcile_document(self, document, journal_entry):
        """Accountant Phase 2: explicit production entry point for document<->journal
        reconciliation. Thin pass-through to `KaizenBrain.reconcile_document` -- never
        called from `cevap_ver`, so ordinary conversational Phase-1 questions are
        completely unaffected."""
        return self.brain.reconcile_document(document, journal_entry)

    def reconcile_collection(self, document, journal_entry, outstanding_receivable=None):
        """Accountant Phase 4: explicit production entry point for receivable-collection
        (kismi/taksitli/tam tahsilat) reconciliation. Thin pass-through to
        `KaizenBrain.reconcile_collection` -- never called from `cevap_ver`, so ordinary
        conversational Phase-1 questions are completely unaffected."""
        return self.brain.reconcile_collection(document, journal_entry, outstanding_receivable)
