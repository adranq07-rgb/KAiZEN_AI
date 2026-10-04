"""İş emri (2026-09-23, "RAG v2 - Faz 1") madde 2: cevap zincirinin görünürlüğü.

`KaizenBrain.answer()`'ın döndürdüğü METİN CEVABIN hiç değişmediğini (yalnız `brain.last_trace`
adında AYRI, ek bir alan eklendiğini) ve trace'in her ana yol için doğru intent/route/confidence/
used_*/refusal_reason ürettiğini kanıtlar. Gerçek Hermes/Ollama'ya hiç dokunmaz -- hepsi sahte
(`FakeProvider`/`FakeAccountingAgent`/`Offline`) sağlayıcılarla, izole bir `dev/workspace/`
sqlite dosyasıyla çalışır (bkz. tests/test_kaizen_brain.py'deki AYNI desen)."""
import tempfile
from pathlib import Path
from uuid import uuid4

from accounting.facts import FactRegistry
from accounting.site_store import SiteStore
from core.kaizen_brain import KaizenBrain
from core.trace import CONFLICTED, PENDING, SUPPORTED, UNKNOWN, VERIFIED
from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore
from memory.knowledge_cards import KnowledgeCardStore
from tests.doubles import NullExperienceMemory


def _workspace():
    root = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root, uuid4().hex


def _cleanup(*paths):
    for db in paths:
        for suffix in ("", "-shm", "-wal"):
            Path(str(db) + suffix).unlink(missing_ok=True)


class FakeProvider:
    def __init__(self, reply="YEREL BİLGİDEN CEVAP"):
        self.reply = reply

    def ask(self, prompt):
        return self.reply


class FakeAccountingAgent:
    def __init__(self, reply="GÜNCEL ARAŞTIRMA"):
        self.reply = reply

    def ask(self, question):
        return self.reply


def test_trace_does_not_change_the_returned_answer_text():
    """En temel kabul ölçütü: trace eklenmeden ÖNCEKİ/SONRAKİ metin cevap birebir aynı olmalı."""
    root, token = _workspace()
    db = root / f"trace_text_{token}.sqlite3"
    try:
        store = LearningStore(db)
        brain = KaizenBrain(
            FakeProvider(), FakeAccountingAgent(),
            brain_manager=BrainManager(learning_store=store, experience_memory=NullExperienceMemory(),
                                        log_dir=tempfile.mkdtemp()),
        )
        answer = brain.answer("matematik: 2 + 2")
        assert answer == "SONUÇ: 4"
        assert brain.last_trace is not None
        assert brain.last_trace.route == "arithmetic" == brain.last_route
    finally:
        _cleanup(db)
    print("KAIZEN TRACE METIN DEGISMEDI TESTI: BASARILI")


def test_trace_arithmetic_and_chart_are_verified():
    root, token = _workspace()
    db = root / f"trace_verified_{token}.sqlite3"
    try:
        store = LearningStore(db)
        brain = KaizenBrain(
            FakeProvider(), FakeAccountingAgent(),
            brain_manager=BrainManager(learning_store=store, experience_memory=NullExperienceMemory(),
                                        log_dir=tempfile.mkdtemp()),
        )
        brain.answer("matematik: 2 + 2")
        assert brain.last_trace.confidence == VERIFIED
        assert brain.last_trace.retrieval_source == "exact_tool"

        # NOT: sade "153 hesap nedir" classify()'i "general"e düşürüyor (bkz. bölüm 4p, Bug #2 --
        # "hesap" tek başına ACCOUNTING_TERMS'te yok). Kesin araç (chart) yine de domain'den
        # BAĞIMSIZ çalışır (_exact_tools, domain kontrolünden önce denenir), o yüzden route yine
        # doğru ("chart") olur -- ama intent burada YANLIŞ ("general") kalırdı. Bu testte intent'in
        # de doğru çıkmasını görmek için ACCOUNTING_TERMS'i gerçekten tetikleyen bir soru kullanıyoruz.
        brain.answer("153 hesap kodu nedir")
        assert brain.last_trace.route == "chart"
        assert brain.last_trace.confidence == VERIFIED
        assert brain.last_trace.intent == "accounting"
    finally:
        _cleanup(db)
    print("KAIZEN TRACE KESIN ARAC = VERIFIED TESTI: BASARILI")


def test_trace_general_domain_uses_model_and_marks_unknown():
    root, token = _workspace()
    db = root / f"trace_general_{token}.sqlite3"
    try:
        store = LearningStore(db)
        brain = KaizenBrain(
            FakeProvider("Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod)."),
            FakeAccountingAgent(),
            brain_manager=BrainManager(learning_store=store, experience_memory=NullExperienceMemory(),
                                        log_dir=tempfile.mkdtemp()),
        )
        # ACCOUNTING_TERMS/OFFICE_TERMS'in HİÇBİRİNİ tetiklemeyen, doğal ama "general"e düşen
        # gerçek bir soru -- bkz. bölüm 4p bulgusu. NOT: eskiden burada örnek "760 ile 770
        # arasındaki fark ne?" idi; iş emri madde 11 kapsamında ChartOfAccounts.answer()'a
        # eklenen çoklu-kod karşılaştırma düzeltmesinden sonra (bkz.
        # accounting/chart_of_accounts.py DÜZELTME notu) o soru artık chart/VERIFIED ile
        # cevaplanıyor (bkz. tests/test_real_world_exam.py, tests/test_classification_failures.py
        # güncellenmiş beklentileri) -- bu yüzden burada rakam/hesap-kodu İÇERMEYEN, hâlâ gerçekten
        # kayıp olan bir karşılaştırma sorusu kullanılıyor.
        # GÜNCELLEME (Learning Loop fazı, kök neden #2): 'Bağkur ile SSK arasındaki fark nedir?' artık
        # doğru biçimde muhasebe/SGK alanına sınıflanıyor (classification düzeltmesi); bu test ise
        # 'muhasebe/ofis alanı DIŞI soru = general' davranışını ölçer, o yüzden gerçekten alan dışı bir
        # soru kullanılır. Asıl doğrulamalar (intent/used_model/UNKNOWN/model_unavailable) AYNEN korunur.
        answer = brain.answer("Türkiye'nin en kalabalık şehri hangisidir?")
        assert brain.last_trace.intent == "general"
        assert brain.last_trace.used_model is True
        assert brain.last_trace.confidence == UNKNOWN
        assert brain.last_trace.refusal_reason == "model_unavailable"
        assert answer  # model "kullanılamıyor" dedi, yerel hafızada da yok -- yine de bir metin döner
    finally:
        _cleanup(db)
    print("KAIZEN TRACE GENEL ALAN = UNKNOWN TESTI: BASARILI")


def test_trace_memory_grounded_is_supported_with_retrieval_score():
    root, token = _workspace()
    db = root / f"trace_memory_{token}.sqlite3"
    try:
        store = LearningStore(db)
        store.add(
            domain="accounting", subject="Temel muhasebe", source_path="ders.pdf",
            source_type="pdf_page", section="Sayfa 1", locator="sayfa 1",
            text="Yevmiye kaydında borç ve alacak tarafları eşit tutarda kaydedilir.",
        )
        brain = KaizenBrain(
            FakeProvider(), FakeAccountingAgent(),
            brain_manager=BrainManager(learning_store=store, experience_memory=NullExperienceMemory(),
                                        log_dir=tempfile.mkdtemp()),
        )
        answer = brain.answer("Yevmiye kaydı nasıl yapılır?")
        assert answer.startswith("YEREL BİLGİDEN CEVAP")
        assert brain.last_trace.route == "memory_grounded"
        assert brain.last_trace.confidence == SUPPORTED
        assert brain.last_trace.used_memory is True
        assert brain.last_trace.retrieval_source == "ders_veya_site"
        assert brain.last_trace.retrieval_score is not None and brain.last_trace.retrieval_score > 0
    finally:
        _cleanup(db)
    print("KAIZEN TRACE YEREL HAFIZA = SUPPORTED TESTI: BASARILI")


def test_trace_pending_card_then_conflicted_after_contradiction():
    root, token = _workspace()
    db = root / f"trace_card_{token}.sqlite3"
    site_db = root / f"trace_card_site_{token}.sqlite3"
    try:
        store = LearningStore(db)
        cards = KnowledgeCardStore(db)
        sites = SiteStore(site_db)
        facts = FactRegistry(site_db)
        facts.rebuild(sites)

        agent = FakeAccountingAgent("ARAŞTIRMA SONUCU: yeni bir bilgi.")
        brain = KaizenBrain(
            FakeProvider(), agent,
            brain_manager=BrainManager(
                learning_store=store, facts=facts, cards=cards,
                experience_memory=NullExperienceMemory(), log_dir=tempfile.mkdtemp(),
            ),
        )
        # 1) Araştırma rotasını sınamak için açıkça güncel bilgi isteyen soru kullan.
        first = brain.answer("Güncel muhasebe: personel yol yardımı nasıl kayıtlanır")
        assert brain.last_trace.route == "research"
        assert first

        # 2) _card_fallback + CONFLICTED yükseltmesini İZOLE test ediyoruz. Gerçek akışta
        # remember_research() bir kartı HEM kart deposuna HEM DE learning_store'a (ders notu
        # gibi) yazar -- bu da bir SONRAKİ soruşta gather_evidence'ın kartı doğrudan bulup
        # memory_grounded route'una gitmesine yol açar, _card_fallback'e hiç uğramadan (ayrı,
        # gerçek bir gözlem -- bkz. iş emri raporu). _card_fallback'in kendisini (ve içindeki
        # CONFLICTED yükseltmesini) sınamak için burada learning_store'a HİÇ dokunmadan, gerçek
        # remember_research()'ün attığı iki adımı (remember + flag_contradiction) birebir taklit
        # ederek kartı doğrudan kart deposuna yazıyoruz.
        card_question = "muhasebe: çalışanlara ödenecek en düşük ücret ne kadar olmalı"
        cards.remember(
            card_question, "accounting",
            "ARAŞTIRMA SONUCU: 2026 yılında brüt asgari ücret 40.000,00 TL'dir.",
            source_label="Kaizen araştırma zinciri (test)", topic=None, block_confirm=True,
        )
        seeded = cards.recall(card_question)
        cards.flag_contradiction(
            seeded["id"],
            "asgari_ucret 2026: araştırma '40000' diyor, parametre defteri (doğrulanmış) '33030' diyor.",
        )

        second = brain.answer(card_question)
        assert brain.last_trace.route == "memory_card_pending"
        assert brain.last_trace.confidence == CONFLICTED
        assert brain.last_trace.retrieval_source == "card"
        assert second  # bir metin döndü (asıl davranış değişmedi)
    finally:
        _cleanup(db, site_db)
    print("KAIZEN TRACE CELISKILI KART = CONFLICTED TESTI: BASARILI")


def test_trace_empty_question_is_refusal():
    root, token = _workspace()
    db = root / f"trace_empty_{token}.sqlite3"
    try:
        store = LearningStore(db)
        brain = KaizenBrain(
            FakeProvider(), FakeAccountingAgent(),
            brain_manager=BrainManager(learning_store=store, experience_memory=NullExperienceMemory(),
                                        log_dir=tempfile.mkdtemp()),
        )
        brain.answer("muhasebe: ")
        assert brain.last_trace.route == "empty"
        assert brain.last_trace.refusal_reason == "empty_question"
        assert brain.last_trace.confidence == UNKNOWN
    finally:
        _cleanup(db)
    print("KAIZEN TRACE BOS SORU = REFUSAL TESTI: BASARILI")


if __name__ == "__main__":
    test_trace_does_not_change_the_returned_answer_text()
    test_trace_arithmetic_and_chart_are_verified()
    test_trace_general_domain_uses_model_and_marks_unknown()
    test_trace_memory_grounded_is_supported_with_retrieval_score()
    test_trace_pending_card_then_conflicted_after_contradiction()
    test_trace_empty_question_is_refusal()
    print("KAIZEN TRACE TESTLERI: BASARILI")
