from accounting.knowledge_base import AccountingKnowledgeBase
from accounting.learning_memory import LearningMemory
from accounting.researcher import AccountingResearcher


class AccountingAgent:
    def __init__(self, provider):
        self.provider = provider
        self.knowledge_base = AccountingKnowledgeBase()
        self.learning_memory = LearningMemory()
        self.researcher = AccountingResearcher(provider)

    def ask(self, question):
        question = question.strip()

        if not question:
            return "Kaizen: Muhasebe sorusu bos olamaz."

        # 1. Daha once kullanici tarafindan duzeltilmis bilgi var mi?
        learned = self.learning_memory.get_all()

        normalized_question = " ".join(question.casefold().split())
        for record in reversed(learned):
            if " ".join(record["question"].casefold().split()) == normalized_question:
                return (
                    "KULLANICININ SON DUZELTMESI (guncelligi yeniden dogrulanmadi):\n"
                    f"{record['correct_answer']}"
                )

        # 2. Kaizen'in kendi bilgi tabaninda bilgi var mi?
        knowledge_results = self.knowledge_base.search(question)

        if knowledge_results:
            result = knowledge_results[0]

            answer = result["answer"]

            if result.get("source"):
                answer += f"\n\nKaynak: {result['source']}"

            return answer

        # 3. Bilgi yoksa arastirma katmanina git
        return self.researcher.research(question)

    def learn(
        self,
        question,
        wrong_answer,
        correct_answer,
        user_note=None
    ):
        self.learning_memory.add_correction(
            question=question,
            wrong_answer=wrong_answer,
            correct_answer=correct_answer,
            user_note=user_note
        )

        return "Kaizen: Duzeltme kaydedildi."
