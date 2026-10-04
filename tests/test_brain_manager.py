"""memory.brain_manager.BrainManager: Kaizen'in hafıza alt sistemleri için tek erişim
noktası. Burada BrainManager'ı DOĞRUDAN (KaizenBrain olmadan) test ediyoruz -- amaç,
KaizenBrain'in artık bu arayüzün arkasındaki depoları (learning_store/site_store/facts/
cards) tek tek bilmesine gerek kalmadığını, tüm bu işlevin BrainManager üzerinden de
tam olarak çalıştığını doğrulamak.
"""
import tempfile
import threading
import time
from pathlib import Path

from accounting.facts import FactRegistry
from accounting.site_store import SiteStore
from memory.brain_manager import BrainManager
from memory.knowledge_cards import KnowledgeCardStore
from memory.learning_store import LearningStore
from tests.doubles import NullExperienceMemory


def _wait_until(predicate, timeout=2.0, interval=0.01):
    """Arka plan iş parçacığında biten bir işin sonucunu, sabit bir sleep yerine kısa
    aralıklarla yoklayarak bekler -- testleri gereksiz yere yavaşlatmadan yarış durumunu
    (race condition) önler."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_brain_manager_retrieval_delegates_to_retriever():
    with tempfile.TemporaryDirectory() as folder:
        store = LearningStore(Path(folder) / "learning.sqlite3")
        store.add(
            domain="accounting", subject="Temel muhasebe", source_path="ders.pdf",
            source_type="pdf_page", section="Sayfa 1", locator="sayfa 1",
            text="Fatura, mal veya hizmet satışında satıcının düzenlediği ticari belgedir.",
        )
        brain = BrainManager(learning_store=store, experience_memory=NullExperienceMemory(), log_dir=folder)
        evidence = brain.gather_evidence("Fatura nedir?", "accounting", current=False)
        assert evidence and any("Fatura" in e.text for e in evidence)

        prompt = brain.build_prompt("Fatura nedir?", "accounting", evidence)
        assert "Fatura nedir?" in prompt

        sources = brain.sources_block(evidence)
        assert "Temel muhasebe" in sources

        extractive = brain.extractive_answer("Fatura nedir?", evidence, strict=False)
        assert extractive and "ticari belgedir" in extractive

    print("KAIZEN BRAINMANAGER ARAMA TESTI: BASARILI")


def test_brain_manager_verified_fact_answer_handles_missing_registry():
    with tempfile.TemporaryDirectory() as folder:
        brain = BrainManager(experience_memory=NullExperienceMemory(), log_dir=folder)
        assert brain.verified_fact_answer("2026 asgari ücret kaç?") is None

        site_db = Path(folder) / "site.sqlite3"
        sites = SiteStore(site_db)
        sites.upsert_page(
            url="https://www.alomaliye.com/2026-ucret", source_name="Alomaliye", title="2026 asgari ücret",
            content="2026 yılında brüt asgari ücret aylık 33.030,00 TL olarak uygulanır.",
            published_at="2026-01-05", effective_year=2026,
        )
        facts = FactRegistry(site_db)
        facts.rebuild(sites)
        brain = BrainManager(facts=facts, experience_memory=NullExperienceMemory(), log_dir=folder)
        answer = brain.verified_fact_answer("Asgari ücret 2026 kaç?")
        assert answer and "33.030,00" in answer

    print("KAIZEN BRAINMANAGER DOGRULAMA TESTI: BASARILI")


def test_brain_manager_remember_research_promotes_card_and_learning_store():
    with tempfile.TemporaryDirectory() as folder:
        store = LearningStore(Path(folder) / "learning.sqlite3")
        cards = KnowledgeCardStore(Path(folder) / "learning.sqlite3")
        exam_path = Path(folder) / "auto_exam_candidates.jsonl"
        brain = BrainManager(learning_store=store, cards=cards, exam_candidates_path=exam_path,
                              experience_memory=NullExperienceMemory(), log_dir=folder)

        card = brain.remember_research(
            "reeskont uygulaması nasıl işler",
            "ARAŞTIRMA SONUCU: Bu konu hakkında ayrıntılı bilgi budur.",
        )
        assert card is not None and card["status"] == "pending"

        # beklemede olsa bile hemen kalıcı hafızaya (learning_store) işlenmiş olmalı
        rows = store.search("reeskont uygulaması", domain="accounting")
        assert any(r["source_type"] == "learned" for r in rows)

        recalled = brain.recall_card("reeskont uygulaması nasıl işler")
        assert recalled is not None and recalled["status"] == "pending"

        confirmed = brain.confirm_card("reeskont uygulaması nasıl işler")
        assert confirmed is not None and confirmed["status"] == "confirmed"
        rows = store.search("reeskont uygulaması", domain="accounting")
        assert any("mali müşavir onayladı" in r["subject"] for r in rows)

        # onaylanan konu için altın sınav önerisi dosyaya yazılmış olmalı
        assert exam_path.exists() and "reeskont" in exam_path.read_text(encoding="utf-8").casefold()

    print("KAIZEN BRAINMANAGER OGRENME TESTI: BASARILI")


def test_brain_manager_remember_research_flags_contradiction_with_verified_facts():
    with tempfile.TemporaryDirectory() as folder:
        site_db = Path(folder) / "site.sqlite3"
        sites = SiteStore(site_db)
        for url, source in (
            ("https://www.alomaliye.com/2026-asgari", "Alomaliye"),
            ("https://vergimerkezi.com.tr/2026-asgari", "Vergi Merkezi"),
            ("https://www.muhasebetr.com/2026-asgari", "Muhasebe TR"),
        ):
            sites.upsert_page(
                url=url, source_name=source, title="2026 asgari ücret",
                content="2026 yılında brüt asgari ücret aylık 33.030,00 TL olarak uygulanır.",
                published_at="2026-01-05", effective_year=2026,
            )
        facts = FactRegistry(site_db)
        facts.rebuild(sites)
        assert any(r["status"] == "verified" for r in facts.rows("asgari_ucret_brut"))

        store = LearningStore(Path(folder) / "learning.sqlite3")
        cards = KnowledgeCardStore(Path(folder) / "learning.sqlite3")
        brain = BrainManager(learning_store=store, facts=facts, cards=cards,
                              exam_candidates_path=Path(folder) / "auto_exam_candidates.jsonl",
                              experience_memory=NullExperienceMemory(), log_dir=folder)

        conflicting_answer = "ARAŞTIRMA SONUCU: 2026 yılında brüt asgari ücret 40.000,00 TL'dir."
        brain.remember_research("çalışanlara ödenecek en düşük ücret ne kadar olmalı", conflicting_answer)
        assert cards.stats()["contradictions"] >= 1
        detail = cards.contradictions()[0]["detail"]
        assert "33.030" in detail or "40.000" in detail

    print("KAIZEN BRAINMANAGER CAPRAZ KONTROL TESTI: BASARILI")


def test_brain_manager_remember_research_same_call_contradiction_blocks_confirmation():
    """DÜZELTME (2026-09-23): DÜZELTME ÖNCESİ, bu kart başka (gerçekten bağımsız) bir kaynaktan
    zaten benzer bir cevapla varken, araştırma zincirinden (`remember_research`) gelen ikinci
    benzer cevap -- hit_count>=2 VE independent_source=True olduğu için -- doğrudan 'confirmed'
    yapılırdı; çelişki (`_cross_check`) ancak bu karar verildikten SONRA tespit edilip yalnızca
    bir çelişki KAYDI eklerdi, kartın durumunu geri almazdı. Artık çelişki, kart durumuna karar
    verilmeden ÖNCE (`_find_contradictions`) bulunuyor ve `block_confirm=True` ile bu turun
    kendisinin 'confirmed'a yükselmesini engelliyor."""
    with tempfile.TemporaryDirectory() as folder:
        site_db = Path(folder) / "site.sqlite3"
        sites = SiteStore(site_db)
        for url, source in (
            ("https://www.alomaliye.com/2026-asgari", "Alomaliye"),
            ("https://vergimerkezi.com.tr/2026-asgari", "Vergi Merkezi"),
            ("https://www.muhasebetr.com/2026-asgari", "Muhasebe TR"),
        ):
            sites.upsert_page(
                url=url, source_name=source, title="2026 asgari ücret",
                content="2026 yılında brüt asgari ücret aylık 33.030,00 TL olarak uygulanır.",
                published_at="2026-01-05", effective_year=2026,
            )
        facts = FactRegistry(site_db)
        facts.rebuild(sites)
        assert any(r["status"] == "verified" for r in facts.rows("asgari_ucret_brut"))

        store = LearningStore(Path(folder) / "learning.sqlite3")
        cards = KnowledgeCardStore(Path(folder) / "learning.sqlite3")
        question = "çalışanlara ödenecek en düşük ücret ne kadar olmalı"
        conflicting_answer = "ARAŞTIRMA SONUCU: 2026 yılında brüt asgari ücret 40.000,00 TL'dir."

        # kart, GERÇEKTEN bağımsız başka bir kaynaktan önceden aynı (yanlış) cevapla var --
        # yalnızca bunu taklit etmek için doğrudan cards.remember() kullanılıyor.
        cards.remember(
            question, "accounting", conflicting_answer,
            source_label="başka bir bağımsız kaynak (test)", topic="asgari_ucret_brut",
        )

        brain = BrainManager(learning_store=store, facts=facts, cards=cards,
                              exam_candidates_path=Path(folder) / "auto_exam_candidates.jsonl",
                              experience_memory=NullExperienceMemory(), log_dir=folder)
        card = brain.remember_research(question, conflicting_answer)

        # hit_count>=2 ve independent_source=True olsa bile, AYNI ÇAĞRIDA bulunan çelişki
        # bu turun kartı 'confirmed'a yükseltmesini engellemiş olmalı.
        assert card is not None and card["status"] == "pending"
        assert cards.stats()["contradictions"] >= 1

    print("KAIZEN AYNI TURDA CELISKI ONAYI ENGELLER TESTI: BASARILI")


class FakeExperienceMemory:
    """memory/cognee_memory.py::CogneeMemory'nin senkron genel arayüzünü (remember/recall)
    taklit eder -- gerçek Cognee/Ollama olmadan BrainManager'ın deneyim hafızası cephesini
    (Kademe 2) test etmek için."""

    def __init__(self):
        self.remembered = []
        self.raise_on_remember = False
        self.raise_on_recall = False
        self.recall_result = {"ok": True, "results": []}

    def remember(self, text, dataset=None):
        if self.raise_on_remember:
            raise RuntimeError("cognee kurulu değil (test)")
        self.remembered.append(text)
        return {"ok": True, "status": "completed", "dataset": dataset or "kaizen", "error": None}

    def recall(self, query, dataset=None, top_k=None):
        if self.raise_on_recall:
            raise RuntimeError("Ollama'ya ulaşılamadı (test)")
        return self.recall_result


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_brain_manager_experience_memory_is_additive_and_never_raises():
    # Kademe 2: deneyim hafızası (Cognee), kart/ders notu sisteminin YERİNE değil ONA EK.
    # remember_experience/recall_experience -- Cognee kapalı/kurulu değilse veya hata verirse
    # (gerçek ortamda: config 'enabled=true' ama paket kurulu değilken tam olarak olur) ana
    # akışı ASLA bozmamalı; bu test hem normal çalışmayı hem de hata yutmayı kanıtlar.
    fake = FakeExperienceMemory()
    # log_dir: asagida kasitli olarak istisna firlatilip yakalandigi (raise_on_remember/recall)
    # test edildigi icin, olusan WARNING/ERROR gercek logs/kaizen.log'a degil izole bir gecici
    # klasore yazilsin diye.
    brain = BrainManager(experience_memory=fake, log_dir=tempfile.mkdtemp())

    # background=False: bu testin amacı geçiş/mantık doğruluğunu kanıtlamak, iş parçacığı
    # zamanlamasını değil -- ayrı bir test (aşağıda) arka plan/timeout davranışını kanıtlar.
    brain.remember_experience("Fatura nedir?", "Fatura, ticari bir belgedir.", background=False)
    assert fake.remembered == ["Soru: Fatura nedir?\nCevap: Fatura, ticari bir belgedir."]

    # boş soru/cevap sessizce atlanır
    brain.remember_experience("", "x")
    brain.remember_experience("x", "")
    assert len(fake.remembered) == 1

    fake.recall_result = {"ok": True, "results": [{"text": "Geçmişte benzer bir soru sorulmuştu.", "source": "graph"}]}
    hits = brain.recall_experience("Fatura nedir?")
    assert hits and hits[0]["text"] == "Geçmişte benzer bir soru sorulmuştu."

    fake.recall_result = {"ok": False, "error": "hazır değil", "results": []}
    assert brain.recall_experience("Fatura nedir?") == []

    # Cognee hata fırlatırsa (paket kurulu değil, Ollama kapalı...) BrainManager hatayı yutar
    fake.raise_on_remember = True
    brain.remember_experience("kırılma testi", "cevap")  # exception fırlatmamalı
    fake.raise_on_recall = True
    assert brain.recall_experience("kırılma testi") == []  # exception fırlatmamalı, boş döner

    # deneyim hafızası hiç verilmezse (varsayılan: gerçek CogneeMemory()) constructor patlamaz.
    # ÖNEMLİ: buradan sonra default_brain.remember_experience/recall_experience GERÇEKTEN
    # ÇAĞRILMAZ -- yalnızca kurucunun patlamadığı doğrulanır. Kullanıcının kendi bilgisayarında
    # (cognee kurulu, config'te memory.cognee.enabled=true) bu iki metot GERÇEK Ollama'ya
    # gerçek yazma/okuma yapar; bu bulut ortamında zararsız görünmesi (cognee kurulu değil)
    # yanıltıcıdır. CogneeMemory'nin kendi kapalı/hatalı durumlarda çökmeden "ok": False
    # döndürdüğü zaten tests/test_cognee_memory.py'de tam izolasyonla (sahte cognee modülüyle)
    # kanıtlanıyor -- burada tekrar GERÇEK nesneyle çağırmaya gerek yok, üstelik tehlikeli.
    default_brain = BrainManager()  # kasıtlı varsayılan: yalnız constructor çökmüyor mu diye -- bkz. yorum yukarıda
    assert default_brain.experience is not None

    print("KAIZEN BRAINMANAGER DENEYIM HAFIZASI TESTI: BASARILI")


class SlowExperienceMemory:
    """remember()/recall() yavaş çalışır -- gerçek ortamda Cognee'nin Ollama üzerinden yaptığı
    LLM+embedding çağrısını simüle eder (saniyeler sürebilir). Bu, remember_experience'ın
    (background=True varsayılanıyla) Kaizen'in cevabını ASLA bekletmediğini, recall_experience'ın
    ise `timeout` süresini aştığında sonsuza kadar beklemeyip boş döndüğünü kanıtlamak için
    kullanılır -- tam olarak kullanıcının gerçek makinesinde yaşanan donma sorununun testi."""

    def __init__(self, delay=0.3):
        self.delay = delay
        self.remembered = []

    def remember(self, text, dataset=None):
        time.sleep(self.delay)
        self.remembered.append(text)
        return {"ok": True, "status": "completed", "dataset": dataset or "kaizen", "error": None}

    def recall(self, query, dataset=None, top_k=None):
        time.sleep(self.delay)
        return {"ok": True, "results": [{"text": "geç gelen sonuç", "source": "graph"}]}


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_brain_manager_remember_experience_runs_in_background_and_recall_has_timeout():
    slow = SlowExperienceMemory(delay=0.3)
    brain = BrainManager(experience_memory=slow, log_dir=tempfile.mkdtemp())

    # remember_experience (background=True varsayılan) ANINDA dönmeli -- gerçek `remember()`
    # çağrısının 0,3 saniye sürmesine rağmen çağıran taraf beklememeli.
    started = time.monotonic()
    brain.remember_experience("Yavaş soru", "Yavaş cevap")
    elapsed = time.monotonic() - started
    assert elapsed < 0.1

    # ama arka plan iş parçacığı sonunda gerçekten tamamlanır
    assert _wait_until(lambda: slow.remembered == ["Soru: Yavaş soru\nCevap: Yavaş cevap"], timeout=2.0)

    # recall_experience: verilen timeout gerçek gecikmeden kısaysa süresi dolar ve boş döner,
    # tam gecikmeyi (0,3 sn) beklemez
    started = time.monotonic()
    result = brain.recall_experience("herhangi bir soru", timeout=0.05)
    elapsed = time.monotonic() - started
    assert result == []
    assert elapsed < 0.3

    # yeterli timeout verilirse aynı çağrı normal şekilde sonucu döndürür
    result2 = brain.recall_experience("herhangi bir soru", timeout=2.0)
    assert result2 and result2[0]["text"] == "geç gelen sonuç"

    print("KAIZEN BRAINMANAGER ARKA PLAN VE TIMEOUT TESTI: BASARILI")


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_brain_manager_experience_stats_tracks_written_and_failed():
    """DÜZELTME (2026-09-23, dış inceleme madde 4): eskiden `remember()`'ın döndürdüğü `ok=False`
    hiç kontrol edilmiyordu, istisnalar sessizce yutuluyordu -- 'hafızaya gerçekten yazıldı mı?'
    hiç görünmüyordu. Artık `experience_stats()` ile yazıldı/başarısız sayıları izlenebiliyor
    (background=False -- senkron -- yol üzerinden, kuyruğa hiç girmeden)."""
    fake = FakeExperienceMemory()
    # log_dir: bu test bilerek "failed" (WARNING/ERROR) durumlar uretiyor; gercek logs/kaizen.log'a
    # sizmasin diye izole bir gecici klasor kullaniyoruz.
    brain = BrainManager(experience_memory=fake, log_dir=tempfile.mkdtemp())
    assert brain.experience_stats() == {"queued": 0, "written": 0, "failed": 0, "dropped": 0}

    brain.remember_experience("soru 1", "cevap 1", background=False)
    assert brain.experience_stats()["written"] == 1

    # ok=False dönerse -- istisna YOK ama yazma başarısız -- 'failed' artmalı
    fake.remember = lambda text, dataset=None: {"ok": False, "error": "Ollama yanit vermedi (test)"}
    brain.remember_experience("soru 2", "cevap 2", background=False)
    stats = brain.experience_stats()
    assert stats["written"] == 1 and stats["failed"] == 1

    # istisna fırlatırsa -- eskiden sessizce yutuluyordu -- yine 'failed' artmalı, dışarı sızmamalı
    fake.raise_on_remember = True
    brain.remember_experience("soru 3", "cevap 3", background=False)
    stats = brain.experience_stats()
    assert stats["written"] == 1 and stats["failed"] == 2

    print("KAIZEN DENEYIM HAFIZASI ISTATISTIK TESTI: BASARILI")


class BlockingExperienceMemory:
    """`remember()` çağrıldığında `release` (bir threading.Event) set edilene kadar bloklanır --
    arka plan işçilerini kasıtlı olarak 'meşgul' tutup kuyruğun gerçekten SINIRLI (bounded)
    olduğunu ve dolduğunda yeni yazımların (sohbeti bloklamadan) atlandığını kanıtlamak için."""

    def __init__(self):
        self.release = threading.Event()
        self.calls = []
        self.lock = threading.Lock()

    def remember(self, text, dataset=None):
        with self.lock:
            self.calls.append(text)
        self.release.wait(timeout=5)
        return {"ok": True, "status": "completed", "dataset": dataset or "kaizen", "error": None}

    def recall(self, query, dataset=None, top_k=None):
        return {"ok": True, "results": []}


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_brain_manager_experience_queue_is_bounded_and_drops_when_full():
    """DÜZELTME (2026-09-23, dış inceleme madde 4): eskiden her `remember_experience` çağrısı
    kendi TEKİL (sınırsız) thread'ini açıyordu. Artık sabit sayıda işçi (_EXPERIENCE_WORKERS=2),
    SINIRLI bir kuyruktan (_EXPERIENCE_QUEUE_MAXSIZE=20) besleniyor -- toplam kapasite en fazla
    2 (işlenmekte) + 20 (kuyrukta) = 22'dir. İşçileri kasıtlı olarak meşgul (bloklu) tutup çok
    daha fazla (100) yazım denemesi göndererek, kuyruk dolunca yeni yazımların sessizce değil
    -- sayılarak (`dropped`) ve sohbeti HİÇ bloklamadan -- atlandığını kanıtlıyoruz."""
    blocking = BlockingExperienceMemory()
    # log_dir: bu test bilerek kuyruğu doldurup çok sayıda WARNING/ERROR ürettiği için,
    # BrainManager'ın kendi logger'ı (varsayılanda gerçek logs/kaizen.log) izole edilmezse
    # bu gürültü gerçek proje log dosyasına yazılır -- gecici bir klasöre yönlendiriyoruz.
    with tempfile.TemporaryDirectory() as log_dir:
        brain = BrainManager(experience_memory=blocking, log_dir=log_dir)

        started = time.monotonic()
        for i in range(100):
            brain.remember_experience(f"soru {i}", f"cevap {i}")  # background=True (varsayılan)
        elapsed = time.monotonic() - started
        assert elapsed < 1.0  # 100 çağrının HİÇBİRİ bloklamadı (release hiç set edilmedi)

        stats = brain.experience_stats()
        # sistem en fazla 22 yazımı aynı anda tutabilir (2 işçi + 20 kuyruk) -- 100 denemeden
        # çoğu (en az 100-22=78'i) kesinlikle atlanmış olmalı
        assert stats["dropped"] >= 78
        # geri kalanı: kuyrukta bekleyen + şu an tam da 2 işçinin içinde (henüz written/failed'e
        # işlenmemiş, bloklu remember() çağrısının ortasında) olabilecek en fazla 2 kayıt -- bu
        # yüzden tam 100 değil, 100'e en fazla 2 eksik bir toplam bekleriz (kesin sayım kaçmaz,
        # yalnızca 2 kaydın "işleniyor" durumu ayrı bir sayaçta tutulmuyor).
        accounted = stats["dropped"] + stats["queued"] + stats["written"] + stats["failed"]
        assert 98 <= accounted <= 100

        blocking.release.set()  # işçileri serbest bırak (test hijyeni -- kalan işler hızlıca biter)
        assert _wait_until(lambda: brain.experience_stats()["queued"] == 0, timeout=2.0)

    print("KAIZEN DENEYIM HAFIZASI KUYRUK SINIRI TESTI: BASARILI")


if __name__ == "__main__":
    test_brain_manager_retrieval_delegates_to_retriever()
    test_brain_manager_verified_fact_answer_handles_missing_registry()
    test_brain_manager_remember_research_promotes_card_and_learning_store()
    test_brain_manager_remember_research_flags_contradiction_with_verified_facts()
    test_brain_manager_remember_research_same_call_contradiction_blocks_confirmation()
    test_brain_manager_experience_memory_is_additive_and_never_raises()
    test_brain_manager_remember_experience_runs_in_background_and_recall_has_timeout()
    test_brain_manager_experience_stats_tracks_written_and_failed()
    test_brain_manager_experience_queue_is_bounded_and_drops_when_full()
    print("KAIZEN BRAINMANAGER TESTLERI: BASARILI")
