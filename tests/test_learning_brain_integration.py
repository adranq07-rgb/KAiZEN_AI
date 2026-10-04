"""KAIZEN — BÜYÜK GELİŞTİRME PAKETİ #1, Faz C: Learning Brain / Principle Layer'ın
Shadow modundan Assisted Mode'a KONTROLLÜ entegrasyonunun testleri (iş emri madde 13).

Bu dosya `tests/test_learning_transfer.py` (Principle Layer'ın kendi doğruluğu, transfer
skoru) İLE `tests/test_learning_transfer_redteam.py` (kör red-team) İLE KARIŞTIRILMAZ --
onlar yalnız `PrincipleRetriever.retrieve()`'i izole test eder. Bu dosya AYRI bir soruya
cevap verir: "Principle Layer, `KaizenBrain._answer_core`'un GERÇEK cevap zincirine
BAĞLANDIĞINDA (madde 13: feature-flag'li Assisted Mode) doğru mu davranıyor?" —
özellikle C2 (confidence gate) ve C3 (FACT firewall) burada UÇTAN UCA doğrulanır.

Gate sonucu (Faz B5, bkz. tests/test_learning_transfer_redteam.py::run_redteam_corrected):
Positive %93.8, Negative %100.0, Fact Safety Violations 0/63, regresyon sağlam ->
PRODUCTION GATE PASSED. Bu dosya, gate PASS ettiği için yazılan Faz C entegrasyonunu test eder.
"""
import tempfile
from pathlib import Path
from uuid import uuid4

from core.kaizen_brain import KaizenBrain
from core.trace import VERIFIED, SUPPORTED
from learning.principle_retriever import PrincipleRetriever
from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore
from memory.principle_registry import PrincipleRegistry
from learning.principle_seed import load_principle_seeds
from tests.doubles import NullExperienceMemory

# tests/test_learning_transfer.py::TRANSFER_SCENARIOS[donemsellik]'ten AYNEN alınan B
# (transfer_question) -- yeni bir soru İCAT EDİLMEDİ, zaten kanıtlanmış bir pozitif-transfer
# örneği kullanıldı.
_DONEMSELLIK_QUESTION = (
    "Aralık ayında kullanılan elektrik faturası ocak ayında geldi ve ocakta ödendi, "
    "bu gideri hangi ayın defterine yazmalıyım?"
)
_DONEMSELLIK_EVIDENCE_TEXT = (
    "Dönemsellik ilkesi geregi gelir ve gider tahsil/odeme tarihine degil, ait oldugu "
    "faaliyet donemine gore kayda alinir. Elektrik faturasi gibi donem sonu giderleri "
    "ilgili oldugu ayin defterine yazilir."
)

# Yapisal sinyal ateslemeyen ama Retriever'in (kanit skoru yeterli oldugu icin) yine de
# grounded yola (evidence bulunan) girdigi bir soru (LOW/NONE principle confidence bekleniyor
# -- red-team N21/VOCAB_TRAP ile ayni ruhta, howto/yazilim sorusu).
_NO_SIGNAL_QUESTION = "Muhasebe programimda yevmiye fisi nasil yazdirilir?"
_NO_SIGNAL_EVIDENCE_TEXT = (
    "Muhasebe programinda yevmiye fisi yazdirmak icin ilgili modulden fis secilip yazdir "
    "butonuna basilir."
)


class _CapturingProvider:
    def __init__(self, reply="MODELDEN CEVAP"):
        self.prompt = ""
        self.calls = 0
        self.reply = reply

    def ask(self, prompt):
        self.prompt = prompt
        self.calls += 1
        return self.reply


class _NullAccountingAgent:
    def ask(self, question):
        return "Kaizen: arastirma modeli bu testte kullanilamiyor."


def _workspace():
    root = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root, uuid4().hex


def _cleanup(*paths):
    for db in paths:
        for suffix in ("", "-shm", "-wal"):
            Path(str(db) + suffix).unlink(missing_ok=True)


def _build_brain(learning_store_text, learning_brain_enabled, provider=None,
                  principle_registry_path=None):
    root, token = _workspace()
    learning_db = root / f"lb_{token}.sqlite3"
    store = LearningStore(learning_db)
    store.add(
        domain="accounting", subject="Dönemsellik ders notu", source_path="ders.pdf",
        source_type="pdf_page", section="Sayfa 1", locator="sayfa 1",
        text=learning_store_text,
    )
    provider = provider or _CapturingProvider()
    registry = PrincipleRegistry(
        principle_registry_path or Path(tempfile.mkdtemp()) / "principles.sqlite3"
    )
    load_principle_seeds(registry)
    retriever = PrincipleRetriever(registry)
    brain = KaizenBrain(
        provider, _NullAccountingAgent(),
        brain_manager=BrainManager(
            learning_store=store, experience_memory=NullExperienceMemory(),
            log_dir=tempfile.mkdtemp(),
        ),
        principle_retriever=retriever,
        learning_brain_enabled=learning_brain_enabled,
    )
    return brain, provider, learning_db


def test_learning_brain_flag_off_no_augmentation_default_behavior():
    """C4: bayrak KAPALIYKEN (varsayılan) -- registry verilmiş olsa BİLE -- davranış eski
    sistemle birebir aynı kalmalı: prompt hiç değişmez, trace principle_* alanları boş kalır
    (core/trace.py'nin 'shadow mode'da varsayılan boş' invariant'ı burada da geçerli)."""
    brain, provider, db = _build_brain(_DONEMSELLIK_EVIDENCE_TEXT, learning_brain_enabled=False)
    try:
        answer = brain.answer(_DONEMSELLIK_QUESTION)
        assert answer.startswith("MODELDEN CEVAP")
        assert "LEARNING BRAIN ILKE IPUCU" not in provider.prompt
        assert brain.last_trace.principle_selected is None
        assert brain.last_trace.principle_candidates == ()
        assert brain.last_route == "memory_grounded"
    finally:
        _cleanup(db)
    print("KAIZEN LEARNING BRAIN BAYRAK KAPALI = ESKI DAVRANIS TESTI: BASARILI")


def test_learning_brain_high_confidence_augments_prompt_assisted_mode():
    """C1/C2 (HIGH): bayrak AÇIKKEN, yapısal sinyali net ateşleyen bir soruda prompt'a
    ilke ipucu EKLENİR ve trace.principle_selected doğru ilkeyle dolar -- ama route hâlâ
    'memory_grounded' (C3: asla VERIFIED değil)."""
    brain, provider, db = _build_brain(_DONEMSELLIK_EVIDENCE_TEXT, learning_brain_enabled=True)
    try:
        answer = brain.answer(_DONEMSELLIK_QUESTION)
        assert answer.startswith("MODELDEN CEVAP")
        assert "LEARNING BRAIN ILKE IPUCU" in provider.prompt
        assert "Dönemsellik" in provider.prompt or "donemsellik" in provider.prompt.lower()
        assert brain.last_trace.principle_selected == "donemsellik"
        assert brain.last_trace.principle_confidence == "HIGH"
        assert brain.last_route == "memory_grounded"
        brain._finalize_trace()
        assert brain.last_trace.confidence == SUPPORTED
        assert brain.last_trace.confidence != VERIFIED
    finally:
        _cleanup(db)
    print("KAIZEN LEARNING BRAIN HIGH CONFIDENCE ASSISTED MODE TESTI: BASARILI")


def test_learning_brain_low_none_never_touches_prompt():
    """C2: yapısal sinyal ateşlemeyen bir soruda (LOW/NONE) -- bayrak açık olsa bile --
    prompt HİÇ değişmez; sistem zorla bir ilke seçmez (madde 11), ama trace (Brain Inspector
    için) yine de dolduğu için gözlemlenebilirlik kaybolmaz."""
    brain, provider, db = _build_brain(_NO_SIGNAL_EVIDENCE_TEXT, learning_brain_enabled=True)
    try:
        answer = brain.answer(_NO_SIGNAL_QUESTION)
        assert answer.startswith("MODELDEN CEVAP")
        assert "LEARNING BRAIN ILKE IPUCU" not in provider.prompt
        assert brain.last_trace.principle_confidence in ("LOW", "NONE")
        assert brain.last_trace.principle_selected is None
    finally:
        _cleanup(db)
    print("KAIZEN LEARNING BRAIN LOW/NONE PROMPT'U ETKILEMEZ TESTI: BASARILI")


def test_learning_brain_domain_restricted_to_accounting():
    """Güvenlik sınırı: domain=='accounting' DEĞİLSE (burada 'general', model her zaman
    doğrudan çağrılır) Principle Layer hiç çalışmaz -- bayrak açık olsa bile."""
    brain, provider, db = _build_brain(_DONEMSELLIK_EVIDENCE_TEXT, learning_brain_enabled=True)
    try:
        brain.answer("Bugün hava nasıl olur dersin?")  # domain == general
        assert brain.last_trace.principle_selected is None
        assert brain.last_trace.principle_candidates == ()
        assert "LEARNING BRAIN ILKE IPUCU" not in provider.prompt
    finally:
        _cleanup(db)
    print("KAIZEN LEARNING BRAIN DOMAIN SINIRI (YALNIZ ACCOUNTING) TESTI: BASARILI")


def test_learning_brain_never_reached_by_exact_tools_or_facts():
    """C3 (FACT FIREWALL, ADANMIŞ TEST): kesin araçlar (matematik) ve parametre defteri
    yolları `_maybe_augment_with_principle`'dan ÖNCE dönüyor -- Principle Layer bu sorularda
    hiç çağrılmaz (trace.principle_selected None kalır) VE bu yolların kendi confidence'ı
    (VERIFIED) Learning Brain'den etkilenmeden aynen kalır."""
    brain, provider, db = _build_brain(_DONEMSELLIK_EVIDENCE_TEXT, learning_brain_enabled=True)
    try:
        answer = brain.answer("matematik: 12 * 3")
        assert answer == "SONUÇ: 36"
        assert brain.last_route == "arithmetic"
        assert brain.last_trace.principle_selected is None
        brain._finalize_trace()
        assert brain.last_trace.confidence == VERIFIED
        assert provider.calls == 0  # model/principle hiç çağrılmadı
    finally:
        _cleanup(db)
    print("KAIZEN LEARNING BRAIN FACT FIREWALL (KESIN ARAC HIC ETKILENMEZ) TESTI: BASARILI")


def test_learning_brain_engine_production_default_is_disabled():
    """Missing configuration remains disabled; v1 explicitly enables production."""
    from config.config_manager import ConfigManager
    config = ConfigManager()
    assert config.learning_brain_enabled() is True
    config.config["learning"].pop("learning_brain_enabled")
    assert config.learning_brain_enabled() is False
    print("KAIZEN LEARNING BRAIN URETIM VARSAYILANI KAPALI (config/Kaizen.json) TESTI: BASARILI")


def test_learning_brain_one_line_revert_contract():
    """C4: geri dönüş gerçekten TEK SATIRLIK bir config değişikliği mi -- kod değişikliği
    gerektirmiyor mu? `ConfigManager.learning_brain_enabled()` yalnızca config sözlüğünden
    okur; bellek-içi kopyada bayrağı çevirmek başka hiçbir şeye dokunmadan yansır."""
    from config.config_manager import ConfigManager
    config = ConfigManager()
    config.config["learning"]["learning_brain_enabled"] = False
    assert config.learning_brain_enabled() is False
    config.config["learning"]["learning_brain_enabled"] = True
    assert config.learning_brain_enabled() is True
    print("KAIZEN LEARNING BRAIN TEK SATIRLIK GERI DONUS SOZLESMESI TESTI: BASARILI")


if __name__ == "__main__":
    test_learning_brain_flag_off_no_augmentation_default_behavior()
    test_learning_brain_high_confidence_augments_prompt_assisted_mode()
    test_learning_brain_low_none_never_touches_prompt()
    test_learning_brain_domain_restricted_to_accounting()
    test_learning_brain_never_reached_by_exact_tools_or_facts()
    test_learning_brain_engine_production_default_is_disabled()
    test_learning_brain_one_line_revert_contract()
