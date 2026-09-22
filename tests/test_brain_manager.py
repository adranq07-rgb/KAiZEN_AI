"""memory.brain_manager.BrainManager: Kaizen'in hafıza alt sistemleri için tek erişim
noktası. Burada BrainManager'ı DOĞRUDAN (KaizenBrain olmadan) test ediyoruz -- amaç,
KaizenBrain'in artık bu arayüzün arkasındaki depoları (learning_store/site_store/facts/
cards) tek tek bilmesine gerek kalmadığını, tüm bu işlevin BrainManager üzerinden de
tam olarak çalıştığını doğrulamak.
"""
import tempfile
from pathlib import Path

from accounting.facts import FactRegistry
from accounting.site_store import SiteStore
from memory.brain_manager import BrainManager
from memory.knowledge_cards import KnowledgeCardStore
from memory.learning_store import LearningStore


def test_brain_manager_retrieval_delegates_to_retriever():
    with tempfile.TemporaryDirectory() as folder:
        store = LearningStore(Path(folder) / "learning.sqlite3")
        store.add(
            domain="accounting", subject="Temel muhasebe", source_path="ders.pdf",
            source_type="pdf_page", section="Sayfa 1", locator="sayfa 1",
            text="Fatura, mal veya hizmet satışında satıcının düzenlediği ticari belgedir.",
        )
        brain = BrainManager(learning_store=store)
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
    brain = BrainManager()
    assert brain.verified_fact_answer("2026 asgari ücret kaç?") is None

    with tempfile.TemporaryDirectory() as folder:
        site_db = Path(folder) / "site.sqlite3"
        sites = SiteStore(site_db)
        sites.upsert_page(
            url="https://www.alomaliye.com/2026-ucret", source_name="Alomaliye", title="2026 asgari ücret",
            content="2026 yılında brüt asgari ücret aylık 33.030,00 TL olarak uygulanır.",
            published_at="2026-01-05", effective_year=2026,
        )
        facts = FactRegistry(site_db)
        facts.rebuild(sites)
        brain = BrainManager(facts=facts)
        answer = brain.verified_fact_answer("Asgari ücret 2026 kaç?")
        assert answer and "33.030,00" in answer

    print("KAIZEN BRAINMANAGER DOGRULAMA TESTI: BASARILI")


def test_brain_manager_remember_research_promotes_card_and_learning_store():
    with tempfile.TemporaryDirectory() as folder:
        store = LearningStore(Path(folder) / "learning.sqlite3")
        cards = KnowledgeCardStore(Path(folder) / "learning.sqlite3")
        exam_path = Path(folder) / "auto_exam_candidates.jsonl"
        brain = BrainManager(learning_store=store, cards=cards, exam_candidates_path=exam_path)

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
                              exam_candidates_path=Path(folder) / "auto_exam_candidates.jsonl")

        conflicting_answer = "ARAŞTIRMA SONUCU: 2026 yılında brüt asgari ücret 40.000,00 TL'dir."
        brain.remember_research("çalışanlara ödenecek en düşük ücret ne kadar olmalı", conflicting_answer)
        assert cards.stats()["contradictions"] >= 1
        detail = cards.contradictions()[0]["detail"]
        assert "33.030" in detail or "40.000" in detail

    print("KAIZEN BRAINMANAGER CAPRAZ KONTROL TESTI: BASARILI")


if __name__ == "__main__":
    test_brain_manager_retrieval_delegates_to_retriever()
    test_brain_manager_verified_fact_answer_handles_missing_registry()
    test_brain_manager_remember_research_promotes_card_and_learning_store()
    test_brain_manager_remember_research_flags_contradiction_with_verified_facts()
    print("KAIZEN BRAINMANAGER TESTLERI: BASARILI")
