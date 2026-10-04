"""KAIZEN BÜYÜK GELİŞTİRME PAKETİ #1, Faz H1/F3/H3/H4: Kaizen Desktop iş mantığı katmanı.

BİLİNÇLİ MİMARİ KARAR (bkz. desktop/ARCHITECTURE_DECISION.md): bu modül KASITLI olarak
`tkinter` İTHAL ETMEZ -- Kaizen'in geliştirme/CI ortamında `python3-tk` sistem paketi
KURULU DEĞİL (bkz. mimari kararın "Ortam Kanıtı" bölümü) ve Windows'ta gerçek GUI'yi
GÖREREK doğrulamak yalnızca kullanıcının kendi makinesinde mümkün (Faz K, "User Acceptance
Test"). Bu yüzden `desktop_app.py`'nin (gerçek `tkinter` penceresi) TÜM iş mantığı buraya,
ÇERÇEVEDEN BAĞIMSIZ, saf Python fonksiyon/sınıflara ayrıldı -- `desktop_app.py` yalnızca
ince bir görünüm (view) katmanı olarak kalır ve bu modülü çağırır. Bu ayrım, Faz L'nin
("UI testleri bu ortamda güvenilmezse iş mantığı/adaptör katmanını test et") AÇIKÇA istediği
şeydir: aşağıdaki HER SINIF `tkinter` olmadan, bu bulut ortamında GERÇEKTEN çalıştırılıp test
edilebilir (bkz. tests/test_desktop_adapter.py).

H1 (GERÇEK BACKEND): bu modül iş mantığını YENİDEN YAZMAZ -- `core/engine.py::KaizenEngine`
zaten Kaizen'in TÜM alt sistemlerini (model, hafıza, öğrenme, principle layer) doğru şekilde
kurup `cevap_ver()` ile tek bir gerçek giriş noktası sunuyor; bu modül yalnızca onun
SONUÇLARINI (cevap metni + `engine.brain.last_trace`) kullanıcı arayüzü için biçimlendirir.

F3 (STATUS MODEL, KESİNLİKLE): arayüz backend'in GERÇEKTEN yaptığından FAZLASINI iddia
ETMEMELİDİR. `engine.cevap_ver()` senkron/bloklayan bir çağrıdır -- araştırma/hafıza arama
gibi ARA adımların GERÇEK zamanlı ilerlemesi (iş emrinin örnek verdiği "Hafızada arıyor",
"İnternette araştırıyor" gibi) bu mimaride GÖZLEMLENEMEZ (KaizenBrain'in kendi iç adımlarını
ayrıca enstrümante etmek büyük bir yeniden yazım gerektirir -- KESİNLİKLE YASAK listesi
madde: "büyük bir yeniden yazım"). Bu yüzden `StatusMapper` YALNIZCA İKİ dürüst durumu
gösterir: cağrı SÜRERKEN "Düşünüyor" (bu gerçek -- motor gerçekten çalışıyor), cağrı
BİTİNCE `brain.last_trace.route`'tan türetilen GERÇEK bir özet ("Son yanıt: ..."). Sahte bir
ilerleme animasyonu İCAT EDİLMEDİ.
"""
from dataclasses import dataclass, field

# core/trace.py'deki REFUSAL_*/ROUTE_CONFIDENCE ile AYNI kaynaktan -- burada YİNELENMEZ,
# yalnızca GÖRÜNTÜLEME için Türkçe etiketlere çevrilir.
_ROUTE_LABELS = {
    "correction": "kullanıcı düzeltmesinden",
    "arithmetic": "hesaplayarak (kesin)",
    "journal": "yevmiye motorundan (kesin)",
    "calculator": "hesap makinesinden (kesin)",
    "chart": "hesap planından (kesin)",
    "facts": "parametre defterinden (doğrulanmış)",
    "memory_grounded": "yerel hafızadan (kanıt destekli)",
    "memory_extractive": "yerel hafızadan (doğrudan alıntı)",
    "memory_card_confirmed": "onaylı bilgi kartından",
    "memory_card_pending": "bekleyen bilgi kartından (ikinci doğrulama bekliyor)",
    "research": "internetten araştırılarak",
    "provider": "genel model bilgisiyle (yerel doğrulama yok)",
    "not_found_offline": "bulunamadı",
    "office_missing": "bulunamadı (ofis konusu)",
    "empty": "boş soru",
}

_CONFIDENCE_LABELS = {
    "VERIFIED": "Doğrulanmış",
    "SUPPORTED": "Kaynak destekli",
    "PENDING": "Beklemede (tek kaynak)",
    "CONFLICTED": "Çelişkili",
    "UNKNOWN": "Doğrulanmamış",
}

STATE_STARTING = "starting"
STATE_READY = "ready"
STATE_BUSY = "busy"
STATE_ANSWERED = "answered"
STATE_ENGINE_ERROR = "engine_error"
STATE_ANSWER_ERROR = "answer_error"

_STATE_LABELS_TR = {
    STATE_STARTING: "Başlatılıyor",
    STATE_READY: "Hazır",
    STATE_BUSY: "Düşünüyor",
    STATE_ANSWERED: "Hazır",
    STATE_ENGINE_ERROR: "Hata",
    STATE_ANSWER_ERROR: "Hata",
}


class StatusMapper:
    """F3: backend durumunu -- OLDUĞU GİBİ -- kullanıcıya gösterilecek kısa bir Türkçe
    etikete çevirir. Hiçbir yöntem burada TAHMİN yapmaz; yalnız zaten var olan bilgiyi
    (state adı, `KaizenTrace.route/confidence`) okunabilir hale getirir."""

    @staticmethod
    def label_for_state(state):
        return _STATE_LABELS_TR.get(state, "Bilinmiyor")

    @staticmethod
    def summarize_trace(trace):
        """Cevap bittikten SONRA (senkron çağrı zaten tamamlandığı için dürüstçe
        bilinen) kısa bir özet döner: 'Son yanıt: <route etiketi> (<confidence etiketi>)'.
        `trace` None ise (engine henüz hiç cevap vermediyse) None döner."""
        if trace is None:
            return None
        route_label = _ROUTE_LABELS.get(trace.route, trace.route or "bilinmiyor")
        confidence_label = _CONFIDENCE_LABELS.get(trace.confidence, trace.confidence or "?")
        return f"Son yanıt: {route_label} — {confidence_label}"


@dataclass
class TraceSummary:
    """Sağ bağlam paneli (F1: Kaynaklar/Doğrulama/Güven durumu/kullanılan principle/
    araştırma durumu) için `KaizenTrace`'in NORMAL kullanıcıya uygun alt kümesi --
    teknik ayrıntı (classification/refusal_reason/kod adları) burada YOK, o yalnız
    Brain Inspector'da (bkz. `full_inspector_lines`)."""

    confidence_label: str
    route_label: str
    used_current_research: bool
    principle_hint: object  # (isim, güven) çifti ya da None
    retrieval_score: object


def context_panel_summary(trace):
    """F1: normal kullanıcı görünümü için kısa, teknik olmayan bağlam özeti."""
    if trace is None:
        return None
    return TraceSummary(
        confidence_label=_CONFIDENCE_LABELS.get(trace.confidence, trace.confidence or "?"),
        route_label=_ROUTE_LABELS.get(trace.route, trace.route or "bilinmiyor"),
        used_current_research=bool(trace.used_research),
        principle_hint=(
            (trace.principle_selected, trace.principle_confidence)
            if trace.principle_selected else None
        ),
        retrieval_score=trace.retrieval_score,
    )


def full_inspector_lines(trace):
    """F2 (Brain Inspector, GELİŞTİRİCİ görünümü): `KaizenTrace`'in TÜM alanlarını,
    okunabilir satırlar hâlinde döner -- normal kullanıcı akışından TAMAMEN AYRI bir
    panelde gösterilmek üzere (bkz. desktop_app.py::BrainInspectorWindow). Ham
    `trace.to_dict()`'i OLDUĞU GİBİ kullanır -- yeni bir alan İCAT EDİLMEZ."""
    if trace is None:
        return ["(henüz bir cevap üretilmedi)"]
    data = trace.to_dict()
    lines = []
    for key in (
        "intent", "route", "retrieval_source", "retrieval_score", "confidence",
        "needs_current_data", "used_model", "used_facts", "used_memory", "used_research",
        "refusal_reason", "principle_candidates", "principle_selected",
        "principle_confidence", "principle_rejected", "principle_reason",
    ):
        lines.append(f"{key}: {data.get(key)!r}")
    return lines


class ErrorPresenter:
    """H3: hata yönetimi. Normal kullanıcıya HİÇBİR ZAMAN ham traceback/istisna metni
    gösterilmez -- yalnız kısa, sabit bir Türkçe mesaj (+ Geliştirici paneline/log'a
    bakma yönlendirmesi). Teknik ayrıntı `technical_detail()` ile AYRICA döner, yalnız
    Brain Inspector/log dosyası bu bilgiyi gösterir."""

    _SAFE_MESSAGE = (
        "Kaizen bu isteği işlerken beklenmeyen bir hata oluştu. Sorunu tekrar dener "
        "misin? Sürerse Geliştirici panelinden (Sistem > Geliştirici Modu) ayrıntıyı "
        "kontrol edebilir ya da logs/kaizen.log dosyasına bakabilirsin."
    )

    @classmethod
    def user_message(cls, exc):
        return cls._SAFE_MESSAGE

    @staticmethod
    def technical_detail(exc):
        return f"{type(exc).__name__}: {exc}"


@dataclass
class ConversationTurn:
    role: str          # 'user' | 'kaizen' | 'sistem'
    text: str
    trace: object = None


class ConversationHistory:
    """H4 (KESİNLİKLE, birebir): bu, GUI'nin kendi oturum-içi görüşme listesidir --
    Kaizen'in GERÇEK hafızasıyla (learning_store/site_store/facts/cards/deneyim
    hafızası) HİÇBİR İLGİSİ YOKTUR ve onlara HİÇ dokunmaz. Yalnız pencere açıkken bu
    oturumun ekranda görünen dökümünü tutar; 'Yeni Sohbet' bunu temizler ama Kaizen'in
    kendi hafızasını SIFIRLAMAZ (motor aynı `KaizenEngine` örneği olarak kalır)."""

    def __init__(self):
        self._turns = []

    def add(self, role, text, trace=None):
        turn = ConversationTurn(role=role, text=text, trace=trace)
        self._turns.append(turn)
        return turn

    def clear(self):
        self._turns = []

    def all(self):
        return list(self._turns)

    def __len__(self):
        return len(self._turns)
