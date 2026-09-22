"""BrainManager: Kaizen'in hafıza alt sistemleri (ders notları, toplanan site sayfaları,
yıllık parametre defteri, araştırmadan öğrenilen bilgi kartları) için TEK erişim noktası.

Neden bu sınıf var: Öncesinde `KaizenBrain` dört ayrı hafıza deposunu (learning_store,
site_store, facts, cards) doğrudan kendi içinde tutuyor, aramayı (Retriever), doğrulamayı
(FactRegistry/AccountingConsensus) ve öğrenmeyi (KnowledgeCardStore + learning_store'a
yazma) hepsini kendi metotlarının içine gömüyordu. Bu, hafıza altyapısı değiştiğinde
(ör. ileride yerel bir LLM ile birlikte Cognee/Graphiti/bir embedding-vector veritabanı
eklenirse) `KaizenBrain`'in karar mantığının da değişmesi gerekeceği anlamına geliyordu.

Bu sınıf, `KaizenBrain`'in (ve ileride başka çağıranların) hafızayla ilgili HER ŞEY için
konuştuğu TEK arayüzdür. Ama kendisi dev bir sınıf DEĞİLDİR: aşağıdaki dört sorumluluk
birbirinden ayrı, halihazırda var olan, kendi başına test edilmiş sınıflara verilmiştir;
`BrainManager` bunları bir araya getirip tek bir arayüz olarak sunan bir koordinatördür
(facade) -- iş mantığının çoğunu kendi içine almaz:

  - Arama / retrieval    -> accounting/retriever.py::Retriever
  - Doğrulama            -> accounting/facts.py::FactRegistry (+ accounting/consensus.py)
  - Öğrenme (kart)       -> memory/knowledge_cards.py::KnowledgeCardStore
  - Fiziksel depolama    -> memory/learning_store.py::LearningStore,
                            accounting/site_store.py::SiteStore

Yalnızca "araştırmadan öğrenilen bilgiyi süzüp kalıcı hafızaya işleme" mantığı (kart
oluştur -> çapraz kontrol et -> ders notuna dönüştür -> sınav önerisi yaz) burada
toplanmıştır, çünkü bu adımların hepsi birden fazla depoyu (cards + facts + learning_store)
ilgilendiren TEK bir iş akışıdır ve önceden `KaizenBrain` içinde dağınık haldeydi.

Kapsam dışı bırakılan (bilinçli, Kademe 1 kararı): `AccountingAgent`'ın kendi kullanıcı
düzeltmesi deposu (accounting/learning_memory.py, JSON) burada YOKTUR. O, kendi başına
test edilen (tests/test_accounting.py, tests/test_office_and_commands.py::test_commands)
ayrı ve dar bir bileşendir; `core/commands.py` hâlâ `accounting_agent.learn()` ile
doğrudan konuşur ve `KaizenBrain._correction()` hâlâ `accounting_agent.learning_memory`'yi
okur. Bu, mevcut testleri bozmadan yapılabilecek en güvenli kapsamdı; ileride bu depo da
BrainManager'a taşınabilir (Kademe 2+).
"""
import json
from datetime import date
from pathlib import Path

from accounting.accounting_brain import AccountingBrain
from accounting.retriever import Retriever

_DEFAULT_EXAM_PATH = Path(__file__).resolve().parent.parent / "data" / "auto_exam_candidates.jsonl"


class BrainManager:
    def __init__(self, learning_store=None, site_store=None, facts=None, cards=None,
                 exam_candidates_path=None):
        # --- fiziksel depolama (mevcut, ayrı sınıflar; burada yeniden yazılmaz) ---
        from memory.learning_store import LearningStore
        self.learning_store = learning_store or LearningStore()
        self.site_store = site_store
        self.facts = facts
        self.cards = cards
        self.exam_candidates_path = Path(exam_candidates_path) if exam_candidates_path else _DEFAULT_EXAM_PATH

        # --- arama / retrieval ---
        self.accounting_brain = AccountingBrain(self.learning_store)
        self.retriever = Retriever(self.learning_store, self.site_store, self.accounting_brain)

    # ------------------------------------------------------------------
    # Arama / retrieval (accounting/retriever.py::Retriever'a ince bir cephe)
    # ------------------------------------------------------------------
    def gather_evidence(self, question, domain, current):
        return self.retriever.gather(question, domain, current=current)

    def build_prompt(self, question, domain, evidence):
        return self.retriever.build_prompt(question, domain, evidence)

    def sources_block(self, evidence):
        return self.retriever.sources_block(evidence)

    def extractive_answer(self, question, evidence, strict):
        return self.retriever.extractive_answer(question, evidence, strict=strict)

    # ------------------------------------------------------------------
    # Doğrulama / yıllık parametre defteri (accounting/facts.py::FactRegistry'a cephe)
    # ------------------------------------------------------------------
    def verified_fact_answer(self, question):
        if self.facts is None:
            return None
        try:
            return self.facts.answer(question)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Öğrenilen bilgi kartları: kendi kendini geliştiren beyin
    # (memory/knowledge_cards.py::KnowledgeCardStore'a cephe + çapraz iş akışı)
    # ------------------------------------------------------------------
    def recall_card(self, question):
        if self.cards is None:
            return None
        return self.cards.recall(question)

    def remember_research(self, question, answer_text):
        """Araştırma zincirinin (Hermes ya da yarın onun yerini alacak başka bir sağlayıcı)
        verdiği cevabı bilgi kartı olarak süzer, süzgeçten geçmiş parametre defteriyle
        çapraz kontrol eder, kalıcı ders notuna (learning_store) işler ve -doğrulanmışsa-
        altın sınav önerisi bırakır. Oluşan/güncellenen kartı döner (yoksa None)."""
        if self.cards is None:
            return None
        topic = None
        if self.facts is not None:
            matched = self.facts.find_topic(question)
            topic = matched.id if matched else None
        if topic is None:
            topic = self.accounting_brain.classify_topic(question)
        status, _ = self.cards.remember(
            question, "accounting", answer_text,
            source_label="Kaizen araştırma zinciri (şu an Hermes; yalnız işçi, sağlayıcı değişebilir)",
            topic=topic,
        )
        card = self.cards.recall(question)
        if card is None:
            return None
        self._cross_check(card)
        self._promote_card(card)  # beklemede olsa bile kalıcı hafızaya (etiketiyle) yazılır
        if status == "confirmed":
            self._suggest_exam_question(card)
        return card

    def _cross_check(self, card):
        """Araştırmanın söylediği rakamı, süzgeçten geçmiş parametre defteriyle çapraz kontrol eder."""
        if self.facts is None:
            return
        try:
            from accounting.consensus import AccountingConsensus
            from accounting.facts import FactExtractor
        except ImportError:
            return
        extractor = FactExtractor(self.facts.topics)
        page = {"content": card["answer"], "url": "kaizen://arastirma", "effective_year": None}
        for candidate in extractor.extract(page):
            verified = next(
                (r for r in self.facts.rows(candidate.topic)
                 if r["year"] == candidate.effective_year and r["status"] == "verified"), None,
            )
            if verified is None:
                continue
            if AccountingConsensus._normalize_value(verified["value"]) != AccountingConsensus._normalize_value(candidate.value):
                self.cards.flag_contradiction(
                    card["id"],
                    f"{candidate.topic} {candidate.effective_year}: araştırma '{candidate.value}' diyor, "
                    f"parametre defteri (doğrulanmış) '{verified['value']}' diyor.",
                )

    def _promote_card(self, card):
        """Kartı (beklemede olsa da, doğrulanmış olsa da) kalıcı hafızaya (learning_store) yazar/günceller."""
        if self.learning_store is None or card is None:
            return
        source_path = f"brain/learned/{card['id']}"
        self.learning_store.remove_by_source(source_path, "learned")
        if card["status"] == "confirmed":
            subject = "Kaizen öğrenilen bilgi (araştırmayla öğrenildi, mali müşavir onayladı)"
            text = card["answer"]
        else:
            subject = "Kaizen öğrenilen bilgi (araştırmayla öğrenildi, onay bekliyor)"
            text = (
                "NOT: Bu bilgi araştırma zincirinden (şu an Hermes) öğrenildi; mali müşavir henüz "
                "'onayla: <soru>' ile onaylamadı, ikinci bağımsız doğrulama görmedi.\n\n" + card["answer"]
            )
        self.learning_store.add(
            domain=card["domain"], subject=subject, source_path=source_path, source_type="learned",
            section=card["question"][:160], locator=None, text=text,
        )

    def _suggest_exam_question(self, card):
        """Öğrenilen konuyu altın sınava eklenmesi için öneri dosyasına yazar (otomatik eklemez)."""
        path = self.exam_candidates_path
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "question": card["question"], "topic": card.get("topic"),
            "excerpt": card["answer"][:280], "created_at": date.today().isoformat(),
            "not": "Kaizen bu konuyu doğruladı; incele ve uygun görürsen tests/test_golden_exam.py içine ekle.",
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def confirm_card(self, question):
        """Mali müşavirin `onayla: <soru>` komutuyla bekleyen bir kartı elle onaylaması."""
        if self.cards is None:
            return None
        card = self.cards.confirm(question)
        if card is not None:
            self._promote_card(card)
            self._suggest_exam_question(card)
        return card
