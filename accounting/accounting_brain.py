class AccountingBrain:
    """Selects course evidence from the correct accounting discipline."""

    TOPICS = {
        "financial_accounting": {
            "terms": {"yevmiye", "bilanço", "bilanco", "fatura", "kayıt", "kayit", "hesap kodu", "tek düzen", "tekduzen", "kapanış", "kapanis", "dönem sonu", "donem sonu", "envanter"},
            "sources": {"genel muhasebe", "genelmuh", "finansal muhasebe", "finansal tablolar"},
        },
        "tax": {
            "terms": {"vergi", "kdv", "vuk", "gelir vergisi", "kurumlar vergisi", "amortisman", "beyanname", "stopaj"},
            "sources": {"gvkvkdv", "vuk", "vergi hukuku"},
        },
        "cost_accounting": {
            "terms": {"maliyet", "üretim", "uretim", "gider dağıtım", "gider dagitim", "safha", "sipariş maliyet"},
            "sources": {"maliyet"},
        },
        "audit": {
            "terms": {"denetim", "denetçi", "denetci", "kanıt", "kanit", "bağımsız denetim", "bagimsiz denetim"},
            "sources": {"denetim"},
        },
        "commercial_law": {
            "terms": {"ticaret hukuku", "şirket", "sirket", "anonim", "limited", "borçlar hukuku", "borclar hukuku"},
            "sources": {"hukuk", "ticaret hukuku", "borclar hukuku", "borçlar hukuku"},
        },
        "professional_law": {
            "terms": {"meslek hukuku", "smmm", "ymm", "türmob", "turmob", "meslek mensubu"},
            "sources": {"meslek hukuku"},
        },
    }

    def __init__(self, learning_store):
        self.learning_store = learning_store

    @classmethod
    def classify_topic(cls, question):
        normalized = " ".join(question.casefold().split())
        scores = {
            topic: sum(len(term.split()) for term in rules["terms"] if term in normalized)
            for topic, rules in cls.TOPICS.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] else "financial_accounting"

    def retrieve(self, question, limit=5):
        topic = self.classify_topic(question)
        candidates = self.learning_store.search(question, domain="accounting", limit=30)
        source_hints = self.TOPICS[topic]["sources"]

        def source_match(row):
            label = f"{row['subject']} {row.get('section') or ''}".casefold()
            return any(hint in label for hint in source_hints)

        # Elle derlenmiş (curated) şablonlar önce, sonra konuya uygun ders kaynakları, sonra kalanlar
        curated = [row for row in candidates if row.get("source_type") == "curated"]
        preferred = [row for row in candidates if source_match(row) and row not in curated]
        remaining = [row for row in candidates if row not in curated and not source_match(row)]
        return topic, (curated + preferred + remaining)[:limit]
