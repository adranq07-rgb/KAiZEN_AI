class AccountingKnowledgeBase:
    def __init__(self):
        self.knowledge = {}

    def add(self, topic, question, answer, source=None):
        if topic not in self.knowledge:
            self.knowledge[topic] = []

        self.knowledge[topic].append({
            "question": question,
            "answer": answer,
            "source": source
        })

    def search(self, question):
        results = []
        normalized_question = " ".join(question.casefold().split())

        for topic, entries in self.knowledge.items():
            for entry in entries:
                saved_question = " ".join(entry["question"].casefold().split())

                if saved_question == normalized_question:
                    results.append({
                        "topic": topic,
                        "question": entry["question"],
                        "answer": entry["answer"],
                        "source": entry["source"]
                    })

        return results

    def count(self):
        return sum(
            len(entries)
            for entries in self.knowledge.values()
        )
