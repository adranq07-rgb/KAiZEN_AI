from accounting.accounting_brain import AccountingBrain


class FakeStore:
    def search(self, question, domain=None, limit=30):
        return [
            {"subject": "D01 Denetim Ders Notlari", "section": "Denetim", "text": "dönem sonu denetim testi"},
            {"subject": "genel muhasebe kaynak 2", "section": "Sayfa 195", "text": "dönem sonu envanter ve kapanış"},
        ]


def test_accounting_brain():
    brain = AccountingBrain(FakeStore())
    topic, rows = brain.retrieve("Dönem sonu kapanış kaydı nasıl yapılır?")
    assert topic == "financial_accounting"
    assert rows[0]["subject"] == "genel muhasebe kaynak 2"
    assert brain.classify_topic("KDV beyannamesi") == "tax"
    assert brain.classify_topic("Üretim maliyet dağıtımı") == "cost_accounting"
    assert brain.classify_topic("Bağımsız denetim kanıtı") == "audit"
    print("KAIZEN MUHASEBE BEYNI TESTI: BASARILI")
