from pathlib import Path
from uuid import uuid4

from accounting.facts import FactRegistry
from accounting.site_store import SiteStore
from core.kaizen_brain import KaizenBrain
from memory.learning_store import LearningStore


class FakeProvider:
    def __init__(self, reply="YEREL BİLGİDEN CEVAP"):
        self.prompt = ""
        self.calls = 0
        self.reply = reply

    def ask(self, prompt):
        self.prompt = prompt
        self.calls += 1
        return self.reply


class FakeAccountingAgent:
    def __init__(self, reply="GÜNCEL ARAŞTIRMA"):
        self.question = None
        self.reply = reply

    def ask(self, question):
        self.question = question
        return self.reply


def _workspace():
    root = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root, uuid4().hex


def _cleanup(*paths):
    for db in paths:
        for suffix in ("", "-shm", "-wal"):
            Path(str(db) + suffix).unlink(missing_ok=True)


def test_kaizen_brain():
    root, token = _workspace()
    db = root / f"brain_{token}.sqlite3"
    site_db = root / f"brain_site_{token}.sqlite3"
    try:
        store = LearningStore(db)
        store.add(
            domain="accounting", subject="Temel muhasebe", source_path="ders.pdf",
            source_type="pdf_page", section="Sayfa 1", locator="sayfa 1",
            text="Yevmiye kaydında borç ve alacak tarafları eşit tutarda kaydedilir.",
        )
        provider = FakeProvider()
        accounting = FakeAccountingAgent()
        brain = KaizenBrain(provider, accounting, store)

        # kesin araçlar: model çağrılmaz
        assert brain.answer("matematik: 0,1 + 0,2") == "SONUÇ: 0,3"
        assert brain.answer("matematik: 1.250,50 * 3") == "SONUÇ: 3.751,5"
        assert brain.answer("1000000/8") == "SONUÇ: 125.000"
        assert provider.calls == 0
        assert brain.answer("muhasebe: ") == "Kaizen: Muhasebe sorusu bos olamaz."

        # yerel hafıza: model yorumlar, kaynaklar deterministik eklenir
        answer = brain.answer("Yevmiye kaydı nasıl yapılır?")
        assert answer.startswith("YEREL BİLGİDEN CEVAP")
        assert "KAYNAKLAR" in answer and "Temel muhasebe" in answer
        assert "Yevmiye kaydında" in provider.prompt
        assert brain.last_route == "memory_grounded"

        # güncel soru + yerel kanıt yok -> araştırma zinciri
        assert brain.answer("2026 amortisman sınırı nedir?") == "GÜNCEL ARAŞTIRMA"
        assert accounting.question == "2026 amortisman sınırı nedir?"

        # ofis konusu ders hafızasında yoksa uydurmaz
        assert "yerel hafızada doğrulanmış bilgi yok" in brain.answer("Excel pivot nasıl yapılır?")
    finally:
        _cleanup(db, site_db)

    print("KAIZEN BEYIN YONLENDIRME TESTI: BASARILI")


def test_brain_independent_of_model():
    """Hermes/model kapalıyken (çevrimdışı) Kaizen hâlâ hesap, kayıt, hesap planı ve parametre cevaplar."""
    root, token = _workspace()
    db = root / f"brain_off_{token}.sqlite3"
    site_db = root / f"brain_off_site_{token}.sqlite3"
    try:
        store = LearningStore(db)
        sites = SiteStore(site_db)
        for url, source, text in (
            ("https://www.alomaliye.com/2026-ucret", "Alomaliye", "2026 yılında brüt asgari ücret 33.030,00 TL olarak uygulanır. Bu tutar 1 Ocak 2026 itibarıyla geçerlidir."),
            ("https://vergimerkezi.com.tr/ucret-2026", "Vergi Merkezi", "Brüt asgari ücret 2026 yılı için aylık 33.030,00 TL'dir. Net asgari ücret ayrıca hesaplanır."),
        ):
            sites.upsert_page(url=url, source_name=source, title="2026 asgari ücret", content=text, published_at="2026-01-05", effective_year=2026)
        facts = FactRegistry(site_db)
        facts.rebuild(sites)

        class Offline:
            def ask(self, prompt):
                return "Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod); yalnız yerel hafızadan cevap verebilirim."

        class Agent:
            def ask(self, question):
                return Offline().ask(question)

        brain = KaizenBrain(Offline(), Agent(), store, sites, facts)

        assert brain.answer("matematik: 500,50 + 750") == "SONUÇ: 1.250,5"
        journal = brain.answer("10.000 TL + %20 KDV ile mal alındı, yevmiye kaydı nedir?")
        assert "153 Ticari Mallar" in journal and "12.000,00" in journal and brain.last_route == "journal"
        assert "100 Kasa" in brain.answer("Kasa hesabının kodu kaç?") and brain.last_route == "chart"
        assert "KDV oranını belirtmediniz" in brain.answer("1.000 TL KDV hesapla")

        fact = brain.answer("Asgari ücret 2026 kaç?")
        assert "33.030,00" in fact and "uzlaşı" in fact and brain.last_route == "facts"

        # bilgi yoksa uydurmaz
        unknown = brain.answer("Kıdem tazminatı tavanı 2026 nedir?")
        assert "uydurmayacağım" in unknown and brain.last_route == "not_found_offline"
    finally:
        _cleanup(db, site_db)

    print("KAIZEN BAGIMSIZ CALISMA TESTI: BASARILI")


def test_brain_current_question_uses_site_memory():
    root, token = _workspace()
    db = root / f"brain_site_q_{token}.sqlite3"
    site_db = root / f"brain_site_q2_{token}.sqlite3"
    try:
        store = LearningStore(db)
        sites = SiteStore(site_db)
        sites.upsert_page(
            url="https://www.vergiport.com/fatura", source_name="Vergiport", title="Fatura sınırı 2026",
            content="Tüketiciye yapılan satışlarda fatura düzenleme sınırı 2026 yılı için 30.000 TL olarak belirlenmiştir.",
            published_at="2026-01-02", effective_year=2026,
        )
        provider = FakeProvider("SONUÇ: 30.000 TL [1]")
        accounting = FakeAccountingAgent()
        brain = KaizenBrain(provider, accounting, store, sites, None)
        answer = brain.answer("2026 fatura düzenleme sınırı nedir?")
        assert answer.startswith("SONUÇ: 30.000 TL") and "https://www.vergiport.com/fatura" in answer
        assert accounting.question is None  # yerelde bulundu, Hermes'e gidilmedi
        assert "yıl: 2026" in provider.prompt

        # model "kanıtta yok" derse araştırmaya geçer
        provider.reply = "Bu bilgi yerel hafızada bulunamadı."
        assert brain.answer("2026 fatura düzenleme sınırı nedir?") == "GÜNCEL ARAŞTIRMA"
    finally:
        _cleanup(db, site_db)

    print("KAIZEN GUNCEL SORU HAFIZA TESTI: BASARILI")
