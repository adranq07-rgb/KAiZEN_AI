"""Kendi kendini geliştiren beyin: araştırmadan öğrenme, kalıcı hafızaya işleme, çapraz kontrol."""
import tempfile
from pathlib import Path

from accounting.facts import FactRegistry
from accounting.site_store import SiteStore
from core.kaizen_brain import KaizenBrain
from memory.knowledge_cards import KnowledgeCardStore
from memory.learning_store import LearningStore


class CountingAgent:
    """Araştırma zincirini taklit eder ve kaç kez çağrıldığını sayar (Hermes çağrısı pahalıdır)."""

    def __init__(self, reply="ARAŞTIRMA SONUCU: örnek cevap metni burada."):
        self.reply = reply
        self.calls = 0
        self.last_question = None

    def ask(self, question):
        self.calls += 1
        self.last_question = question
        return self.reply


class Offline:
    def ask(self, prompt):
        return "Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod); yalnız yerel hafızadan cevap verebilirim."


def test_knowledge_card_store_pending_confirm_and_contradiction():
    with tempfile.TemporaryDirectory() as folder:
        cards = KnowledgeCardStore(Path(folder) / "cards.sqlite3")

        status, hits = cards.remember(
            "Reeskont nasıl hesaplanır", "accounting",
            "Reeskont, vadeli senetlerin bugünkü değere indirgenmesidir.",
            source_label="test araştırma", topic="reeskont",
        )
        assert status == "pending" and hits == 1

        # aynı soruya çok benzer bir cevap ikinci bağımsız turda gelirse kendiliğinden doğrulanır
        status, hits = cards.remember(
            "Reeskont nasıl hesaplanır", "accounting",
            "Reeskont, vadeli senetlerin bugünkü değere indirgenmesi işlemidir.",
            source_label="test araştırma 2", topic="reeskont",
        )
        assert status == "confirmed" and hits == 2

        # tamamen alakasız bir cevap gelirse (mevzuat değişmiş olabilir) tekrar beklemeye düşer
        status, hits = cards.remember(
            "Reeskont nasıl hesaplanır", "accounting",
            "Kasa sayımında noksan çıkarsa 197 hesabına borç yazılır.",
            source_label="test araştırma 3", topic="reeskont",
        )
        assert status == "pending" and hits == 1

        # geri çağırma: birebir aynı soru
        found = cards.recall("Reeskont nasıl hesaplanır")
        assert found is not None and found["status"] == "pending"

        # geri çağırma: anlamca yakın ama farklı yazılmış soru
        found_fuzzy = cards.recall("Reeskont hesaplama nasıl yapılır")
        assert found_fuzzy is not None and found_fuzzy["id"] == found["id"]

        # mali müşavir onayı
        confirmed = cards.confirm("Reeskont nasıl hesaplanır")
        assert confirmed is not None and confirmed["status"] == "confirmed"
        assert cards.recall("Reeskont nasıl hesaplanır")["status"] == "confirmed"

        # çelişki kaydı
        cards.flag_contradiction(confirmed["id"], "reeskont 2026: araştırma '%50' diyor, defter '%45' diyor.")
        assert len(cards.contradictions()) == 1
        assert cards.stats()["contradictions"] == 1

    print("KAIZEN BILGI KARTI TESTI: BASARILI")


def test_brain_learns_from_research_and_avoids_repeat_calls():
    with tempfile.TemporaryDirectory() as folder:
        store = LearningStore(Path(folder) / "learning.sqlite3")
        cards = KnowledgeCardStore(Path(folder) / "learning.sqlite3")
        agent = CountingAgent("ARAŞTIRMA SONUCU: Bu konu hakkında ayrıntılı bilgi budur.")
        brain = KaizenBrain(
            Offline(), agent, learning_store=store, cards=cards,
            exam_candidates_path=Path(folder) / "auto_exam_candidates.jsonl",
        )

        question = "muhasebe: reeskont uygulaması nasıl işler"

        first = brain.answer(question)
        assert first == agent.reply
        assert brain.last_route == "research"
        assert agent.calls == 1

        # kart beklemede olarak kaydedilmiş olmalı
        card = cards.recall("reeskont uygulaması nasıl işler")
        assert card is not None and card["status"] == "pending"

        # aynı soru ikinci kez sorulunca artık araştırmaya gitmeden hafızadan cevap verir.
        # Bekleyen kart da kalıcı hafızaya etiketiyle yazıldığı için (BrainManager._promote_card)
        # cevap ders notu yolundan gelebilir; önemli olan onay uyarısının korunması.
        second = brain.answer(question)
        assert agent.calls == 1  # tekrar araştırma yapılmadı
        assert brain.last_route in ("memory_card_pending", "memory_extractive")
        assert "ikinci bağımsız doğrulama görmedi" in second
        assert "Bu konu hakkında ayrıntılı bilgi budur" in second

        # mali müşavir onaylayınca kart kalıcı hafızaya (learning_store) yazılır
        confirmed = brain.confirm_card("reeskont uygulaması nasıl işler")
        assert confirmed is not None and confirmed["status"] == "confirmed"
        learned_rows = store.search("reeskont uygulaması", domain="accounting")
        assert any(r["source_type"] == "learned" for r in learned_rows)

        # onaydan sonra artık normal (doğrulanmış) hafıza yolundan, notsuz cevap verir
        third = brain.answer(question)
        assert agent.calls == 1
        assert "ikinci bağımsız doğrulama görmedi" not in third

        # altın sınav önerisi dosyasına yazılmış olmalı
        exam_file = Path(folder) / "auto_exam_candidates.jsonl"
        assert exam_file.exists() and "reeskont" in exam_file.read_text(encoding="utf-8").casefold()

    print("KAIZEN ARASTIRMADAN OGRENME TESTI: BASARILI")


def test_brain_cross_checks_research_against_verified_facts():
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
        agent = CountingAgent()
        brain = KaizenBrain(
            Offline(), agent, learning_store=store, facts=facts, cards=cards,
            exam_candidates_path=Path(folder) / "auto_exam_candidates.jsonl",
        )

        # "asgari ücret" kelimesi soruda geçerse doğrudan parametre defterinden (facts) cevaplanır;
        # burada amaç, ARAŞTIRMANIN (ör. Hermes) verdiği serbest metin cevabın parametre defteriyle
        # çapraz kontrol edilmesini test etmek, o yüzden _remember_research doğrudan çağrılıyor
        # (gerçek akışta bu, brain.answer() içinde araştırma başarılı olduğunda otomatik tetiklenir).
        conflicting_answer = "ARAŞTIRMA SONUCU: 2026 yılında brüt asgari ücret 40.000,00 TL'dir."
        brain._remember_research("çalışanlara ödenecek en düşük ücret ne kadar olmalı", conflicting_answer)
        assert cards.stats()["contradictions"] >= 1
        detail = cards.contradictions()[0]["detail"]
        assert "33.030" in detail or "40.000" in detail

    print("KAIZEN CAPRAZ KONTROL TESTI: BASARILI")


if __name__ == "__main__":
    test_knowledge_card_store_pending_confirm_and_contradiction()
    test_brain_learns_from_research_and_avoids_repeat_calls()
    test_brain_cross_checks_research_against_verified_facts()
