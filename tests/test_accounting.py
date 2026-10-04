from accounting.accounting_agent import AccountingAgent
from datetime import date
from uuid import uuid4
from pathlib import Path
from accounting.learning_memory import LearningMemory


class FakeProvider:
    def __init__(self):
        self.prompt = None

    def research(self, prompt):
        self.prompt = prompt
        return "KAYNAKLI ARASTIRMA"


def test_accounting():
    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    memory_file = workspace / f"corrections_{uuid4().hex}.json"

    provider = FakeProvider()
    # learning_memory_path: gercek data/accounting_learning.json'a hic dokunmadan izole
    # bir gecici dosya kullanilir (bkz. KaizenEngine/AccountingAgent test izolasyonu).
    agent = AccountingAgent(provider, learning_memory_path=memory_file)

    agent.knowledge_base.add(
        "fatura", "Fatura kaydi nedir?", "Ornek cevap", "Ornek kaynak"
    )
    assert agent.ask("  fatura kaydi NEDIR? ") == "Ornek cevap\n\nKaynak: Ornek kaynak"

    answer = agent.ask("Fatura tutari nasil hesaplanir?")
    assert answer == "KAYNAKLI ARASTIRMA"
    assert "Fatura tutari nasil hesaplanir?" in provider.prompt
    assert date.today().isoformat() in provider.prompt
    assert str(date.today().year - 2) in provider.prompt
    # Araştırma zinciri de, yerel hafıza yolu (accounting/retriever.py::build_prompt) gibi,
    # her zaman "mali müşavir gibi düşün" çerçevesiyle konuşmalı -- tutarlı ses.
    assert "mali müşavir" in provider.prompt

    try:
        agent.learn("Oran nedir?", "ilk", "Eski cevap")
        agent.learn("  Oran   nedir? ", "Eski cevap", "Yeni cevap")
        # Reload to verify the newest correction survives a restart.
        agent.learning_memory = LearningMemory(memory_file)
        result = agent.ask("ORAN nedir?")
        assert "Yeni cevap" in result and "Eski cevap" not in result
        assert "guncelligi yeniden dogrulanmadi" in result
    finally:
        memory_file.unlink(missing_ok=True)

    print("KAIZEN MUHASEBE TESTI: BASARILI")


class FakeAskProvider:
    def __init__(self):
        self.prompt = None

    def ask(self, prompt):
        self.prompt = prompt
        return "DOGRULAMA CEVABI"


def test_accounting_agent_verify_document():
    # 'excel bilgisini teyit et' / 'hesaplarımı kontrol et' istegini karsilayan
    # AccountingAgent.verify_document -- kullanicinin kendi belgesini (excel/pdf metnine
    # cevrilmis) Kaizen'in dogrulanmis parametre defteriyle karsilastirir.
    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    memory_file = workspace / f"corrections_{uuid4().hex}.json"

    try:
        provider = FakeAskProvider()
        agent = AccountingAgent(provider, learning_memory_path=memory_file)

        result = agent.verify_document("Kira: 1000\nKDV: %20", "- KDV orani (2026): %20")
        assert result == "DOGRULAMA CEVABI"
        assert "mali müşavir" in provider.prompt
        assert "KDV orani (2026): %20" in provider.prompt
        assert "Kira: 1000" in provider.prompt

        assert "boş" in agent.verify_document("   ", "")

        class NoAskProvider:
            pass

        fallback_memory_file = workspace / f"corrections_{uuid4().hex}.json"
        try:
            fallback_agent = AccountingAgent(NoAskProvider(), learning_memory_path=fallback_memory_file)
            assert "desteklemiyor" in fallback_agent.verify_document("x", "")
        finally:
            fallback_memory_file.unlink(missing_ok=True)
    finally:
        memory_file.unlink(missing_ok=True)

    print("KAIZEN MUHASEBE BELGE DOGRULAMA TESTI: BASARILI")


if __name__ == "__main__":
    test_accounting()
    test_accounting_agent_verify_document()
