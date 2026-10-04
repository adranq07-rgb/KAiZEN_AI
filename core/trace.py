"""Kaizen'in cevap zincirinin görünürlüğü (debug/trace).

Bir soru geldiğinde `KaizenBrain._answer_core` sırayla birçok yoldan (düzeltme, kesin
araçlar, parametre defteri, yerel hafıza, araştırma...) geçer; hangi yoldan geçtiği, hangi
kaynağın kullanıldığı ve NEDEN "bulamadım" denildiği eskiden yalnız `self.last_route` (tek bir
kısa etiket) ile görünüyordu. Bu modül, iş emrinin istediği yapılandırılmış izleme nesnesini
tanımlar: `KaizenTrace`. `KaizenBrain.answer()`/`cevap_ver()`'in döndürdüğü METİN CEVAP hiç
değişmez (kullanıcıya giden cevap kirletilmez) -- trace, `self.last_route` ile AYNI desende,
çağrıdan SONRA `brain.last_trace` üzerinden okunur (ayrı bir alan, mevcut genel API bozulmaz).

GÜVEN MODELİ (iş emri madde 8): bir bilginin nereden geldiği ile ne kadar güvenilir olduğu
birbirinden kesin ayrılır. Aşağıdaki altı etiket kullanılır; hiçbiri "embedding ile benzer
bulundu" ile otomatik VERIFIED anlamına gelmez -- doğruluk otoritesi hep facts/consensus'ta kalır:

  FOUND      -- bir şey bulundu (henüz kaynak/doğrulama durumu ayrı değerlendirilmedi)
  SUPPORTED  -- bilginin bir kaynağı var (ders notu/site sayfası) ama facts/consensus'tan
               geçmedi, tek turluk araştırma veya insan onayı da yok
  VERIFIED   -- kesin araç (hesap makinesi/yevmiye/hesap planı), süzgeçten geçmiş parametre
               defteri veya mali müşavirin/kullanıcının açık onayı/düzeltmesi
  PENDING    -- tek kaynaklı bilgi kartı; ikinci bağımsız kaynak veya `onayla:` bekliyor
  CONFLICTED -- bu kart için kapatılmamış bir çelişki kaydı var (facts ile veya kaynaklar
               arasında)
  UNKNOWN    -- güvenilir hiçbir kaynak yok; dürüst "bulamadım" ya da modele çıplak devredildi

REFUSAL_REASON (yalnız nihai cevap bir çeşit "bulamadım"/refuse olduğunda dolu): iş emrinin
verdiği örnek nedenler + bu kod tabanında gözlemlenen birkaç ek durum. Sabit bir liste değil --
yeni bir refuse yolu eklenince buraya yeni bir sabit eklenebilir; testler (`test_engine_isolation.py`
deseninde değil, burada) bilinen köke ait olmayan bir refusal_reason'ı YAKALAMAZ, bu kasıtlı: liste
büyüsün diye zorlamıyoruz, yalnız DOKÜMANTE ediyoruz.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional

FOUND = "FOUND"
SUPPORTED = "SUPPORTED"
VERIFIED = "VERIFIED"
PENDING = "PENDING"
CONFLICTED = "CONFLICTED"
UNKNOWN = "UNKNOWN"

CONFIDENCE_LEVELS = (FOUND, SUPPORTED, VERIFIED, PENDING, CONFLICTED, UNKNOWN)

# route (bkz. KaizenBrain.last_route) -> varsayılan güven etiketi. Bir çelişki bulunursa
# (kartın "confliced" olması) KaizenBrain bunu CONFLICTED'e YÜKSELTİR (bkz. _confidence_for_route).
ROUTE_CONFIDENCE = {
    "correction": VERIFIED,          # kullanıcının kendi düzeltmesi -- en yetkili kaynak
    "arithmetic": VERIFIED,           # Decimal, uydurma yok
    "journal": VERIFIED,              # kesin yevmiye motoru
    "calculator": VERIFIED,           # kesin hesap makinesi
    "chart": VERIFIED,                # Tek Düzen Hesap Planı (config/tdhp.json)
    "facts": VERIFIED,                # süzgeçten geçmiş parametre defteri
    "memory_grounded": SUPPORTED,     # ders notu/site kanıtı var, model yorumluyor
    "memory_extractive": SUPPORTED,   # ders notu/site kanıtından düz alıntı
    "memory_card_confirmed": VERIFIED,  # mali müşavir onayladı
    "memory_card_pending": PENDING,   # tek turluk araştırma, onay bekliyor
    "research": PENDING,              # YENİ başarılı araştırma -- arka planda "pending" karta
                                       # dönüşür ama bu turun metni henüz bu notu taşımıyor
                                       # (bkz. bölüm 4p, "araştırma şeffaflık boşluğu" bulgusu)
    "provider": UNKNOWN,              # yerel katmanların HİÇBİRİNE uğramadan çıplak model cevabı
    "not_found_offline": UNKNOWN,
    "office_missing": UNKNOWN,
    "empty": UNKNOWN,
    # Learning Brain v1 (iş emri madde 13): yalnız learning/decision_bridge.py'nin ürettiği
    # Decision nesnelerinde görünür -- KaizenBrain.last_route BUNU ASLA GERÇEKTEN SETlemez
    # (Principle Layer üretim cevap zincirine bağlı değil, madde 14). Şu an burada tutulma
    # nedeni yalnız "preferred_route bilinen bir rota mı?" kontratını (test_decision_engine_
    # contract.py deseniyle tutarlı) principle-shadow Decision'lar için de sağlamak.
    "principle_shadow": UNKNOWN,
    # Accountant Phase 2: document <-> journal reconciliation is a deterministic
    # comparison (Decimal, no model), same confidence class as journal/calculator/chart.
    "document_reconciliation": VERIFIED,
    # Accountant Phase 4: receivable collection reconciliation is the same deterministic
    # comparison class (Decimal, no model) built on top of document_reconciliation.
    "receivable_collection": VERIFIED,
    # Document & Office Engine: yerel dosya işlemleri deterministiktir (model/belge
    # icerigi uzak uca gitmez -- LOCAL_ONLY), ayni guven sinifi.
    "document_engine": VERIFIED,
}

# refusal_reason sabitleri (iş emrinin verdiği örnekler + gözlemlenen ek durumlar)
REFUSAL_CLASSIFICATION_FAILED = "classification_failed"
REFUSAL_RETRIEVAL_NO_MATCH = "retrieval_no_match"
REFUSAL_RETRIEVAL_THRESHOLD_FAILED = "retrieval_threshold_failed"
REFUSAL_CURRENT_FACT_MISSING = "current_fact_missing"
REFUSAL_RESEARCH_FAILED = "research_failed"
REFUSAL_MODEL_UNAVAILABLE = "model_unavailable"
REFUSAL_EMPTY_QUESTION = "empty_question"
REFUSAL_EXACT_TOOL_NO_MATCH = "exact_tool_no_match"


@dataclass
class KaizenTrace:
    """Bir `answer()` çağrısının izlenebilir kararları. `to_dict()` testlerde/loglarda
    kullanmak için düz bir dict döner (dataclass'ın kendisi de doğrudan okunabilir)."""

    intent: Optional[str] = None               # classify() sonucu: accounting/office/mathematics/general
    route: Optional[str] = None                 # self.last_route ile AYNI değer (tek kaynaktan iki isim)
    retrieval_source: Optional[str] = None       # ders / site / facts / card / exact_tool / provider / None
    retrieval_score: Optional[float] = None      # varsa kapsama/skor (0..1 ya da Retriever skoru)
    confidence: str = UNKNOWN                    # bkz. CONFIDENCE_LEVELS
    needs_current_data: bool = False             # KaizenBrain.needs_current_research(question)
    used_model: bool = False                     # provider.ask()/research() gerçekten çağrıldı mı
    used_facts: bool = False                     # FactRegistry'ye (verified_fact_answer) başvuruldu mu
    used_memory: bool = False                    # ders notu/site (Retriever/BrainManager.gather_evidence) kullanıldı mı
    used_research: bool = False                  # araştırma zinciri (_research_once) çalıştı mı
    refusal_reason: Optional[str] = None         # yalnız nihai cevap refuse ise dolu

    # --- Learning Brain v1 (iş emri madde 12): Principle Layer gözlem alanları -----------
    # TAMAMEN EKLENDİ (additive) -- KaizenBrain._answer_core bu alanları HİÇBİR ZAMAN
    # doldurmaz (Principle Layer şu an KaizenBrain'e bağlı DEĞİL, madde 14: shadow/
    # observational). Yalnız learning/principle_retriever.py::PrincipleRetriever
    # doğrudan çağrılıp learning/trace_bridge.py::fill_principle_trace ile GÖZLEM
    # amaçlı dolduran testlerde kullanılır. Kullanıcıya giden METİN CEVABI bu alanlardan
    # HİÇ ETKİLENMEZ (bkz. modül docstring'i, madde 12: "cevap metnini değiştirmek
    # zorunda değilsin").
    principle_candidates: tuple = ()             # ((principle_id, score), ...) skor azalan sırada
    principle_selected: Optional[str] = None      # seçilen principle_id ya da None
    principle_confidence: Optional[str] = None    # learning.principle_retriever.{HIGH,MEDIUM,LOW,NONE}
    principle_rejected: tuple = ()                 # ((principle_id, reason), ...)
    principle_reason: Optional[str] = None         # insan-okunur seçim/red gerekçesi

    # --- Trace v2 (Learning Loop fazı): GERÇEK akışı gösteren gözlem alanları ---------------
    # DOĞRULUK KURALI: her alan yalnız ilgili olay GERÇEKTEN olduysa dolar. Varsayılan
    # None/0/() "bu olay olmadı ya da ölçülmedi" demektir -- örn. Research Engine hiç
    # çalışmadıysa research_status None kalır, "araştırıldı" gösterilmez. Trace yalnız
    # OBSERVABILITY'dir: bir FACT kaynağı DEĞİLDİR, hiçbir karar buradan okunmaz.
    decision: Optional[str] = None                # answer_exact/answer_facts/answer_memory/
                                                   # answer_research_engine/answer_research_hermes/
                                                   # answer_card/answer_model/answer_correction/refuse
    research_needed: bool = False                  # araştırma yolu GERÇEKTEN çağrıldı (gerekli görüldü)
    research_status: Optional[str] = None          # yalnız Research Engine çalıştıysa (ResearchResult.status)
    search_provider: Optional[str] = None          # yalnız Research Engine çalıştıysa
    search_health: Optional[str] = None            # ResearchResult.search_health
    query_count: int = 0
    result_count: int = 0                          # arama sonucu (henüz kanıt DEĞİL)
    fetched_count: int = 0                         # gerçekten getirilip okunan sayfa
    evidence_count: int = 0                        # gerçek içerikli kanıt parçası
    official_evidence_count: int = 0
    consensus_status: Optional[str] = None         # agreed/partial/conflicted/none (yalnız research çalıştıysa)
    conflict_count: int = 0
    principle_candidate: Optional[str] = None      # seçilmiş ya da en yüksek skorlu ilke adayı (yalnız retriever çalıştıysa)
    experience_candidate: Optional[bool] = None    # bu cevap yeniden kullanılabilir STRATEJİ adayı olarak kaydedildi mi
    experience_reusable: Optional[bool] = None     # önceden onaylı, reusable bir deneyim BU cevabı yönlendirdi mi
    experience_advice: Optional[str] = None        # yönlendiren strateji kimliği (süreç tarifi, FACT değil)
    experience_rejected_reason: Optional[str] = None  # deneyim neden KULLANILMADI (negatif transfer vb.)
    reflection_written: Optional[bool] = None      # None=denenmedi, True/False=kayıt sonucu
    user_feedback_effect: Optional[str] = None     # onayla:/düzelt: sonrası (ayrı çağrıda güncellenir)
    fallback_used: bool = False                    # Research Engine denendi, Hermes devraldı
    elapsed_ms: Optional[int] = None
    strategy: Optional[str] = None
    strategy_source: Optional[str] = None
    strategy_experience_ids: tuple = ()
    experience_id: Optional[str] = None
    reflection_id: Optional[str] = None
    learned_principle_id: Optional[str] = None
    outcome: Optional[str] = None
    verification_result: Optional[str] = None
    deterministic_tool: Optional[str] = None
    retrieval_mode: Optional[str] = None
    lexical_candidate_count: int = 0
    semantic_used: bool = False
    cache_hits: int = 0
    cache_misses: int = 0
    fallback_reason: Optional[str] = None
    latency_breakdown: dict = field(default_factory=dict)
    model_calls: int = 0
    embedding_attempted: bool = False
    embedding_success: bool = False
    semantic_ms: float = 0.0
    scrapling_attempted: bool = False
    scrapling_success: bool = False
    scrapling_latency_ms: float = 0.0
    scrapling_fallback_used: bool = False
    lexical_order: tuple = ()
    semantic_order: tuple = ()
    strategy_consumed: bool = False
    strategy_effect: Optional[str] = None
    # Deprecated schema fields: always zero/false; retained for saved trace readers.
    cognee_recall_attempted: bool = False
    cognee_recall_count: int = 0
    cognee_context_consumed: bool = False
    principle_discovered: Optional[str] = None
    principle_discovery_status: Optional[str] = None
    principle_support_count: int = 0
    principle_selected_for_strategy: bool = False
    retrieved_principle_id: Optional[str] = None
    retrieved_principle_confidence: Optional[str] = None
    strategy_guidance_source: Optional[str] = None
    accounting_reasoning_used: bool = False
    problem_type: Optional[str] = None
    concept_ids: tuple = ()
    principle_ids: tuple = ()
    deterministic_tool_used: bool = False
    current_fact_needed: bool = False
    knowledge_source_types: tuple = ()
    accounting_reasoning_context: Optional[dict] = None
    principle_retrieval_status: str = "NONE_APPLICABLE"
    external_actions: list = field(default_factory=list)
    accounting_pipeline: Optional[dict] = None
    journal_entry: Optional[dict] = None
    invariant_failures: list = field(default_factory=list)
    missing_facts: list = field(default_factory=list)

    # --- Accountant Phase 2: document <-> journal reconciliation (additive) -------------
    # DOGRULUK KURALI (ayni desen, satir 114-117): yalniz reconcile_document_entry()
    # GERCEKTEN cagrildiysa dolar. Normal Phase-1 sorularinda (KaizenBrain.answer()/
    # cevap_ver) bu alanlar hep varsayilan (None/[]) kalir -- cunku o yol reconciliation
    # kodunu hic cagirmaz (bkz. KaizenBrain.reconcile_document, core/kaizen_brain.py).
    document_validation: Optional[dict] = None       # {"document_checks":..., "entry_checks":...}
    reconciliation_status: Optional[str] = None      # MATCH/MISMATCH/INSUFFICIENT_INFORMATION/
                                                      # INVALID_DOCUMENT/INVALID_ENTRY
    discrepancies: list = field(default_factory=list)
    missing_information: list = field(default_factory=list)

    # --- Accountant Phase 4: kismi/taksitli alacak tahsilati (additive) -----------------
    # AYNI DOGRULUK KURALI (satir 199-202): yalniz accounting/receivable_collection.py::
    # reconcile_receivable_collection() GERCEKTEN cagrildiysa dolar. Normal Phase-1
    # sorularinda ve Phase-2/3 reconcile_document cagrilarinda hep None kalir.
    collection_details: Optional[dict] = None        # {"event_type":"receivable_collection",
                                                      #  "collection_type":"partial"/"full"/None,
                                                      #  "payment_account":"100"/"102"/None,
                                                      #  "collected_amount":str/None,
                                                      #  "remaining_receivable":str/None,
                                                      #  "reconciliation_status":str}

    def to_dict(self):
        return asdict(self)
