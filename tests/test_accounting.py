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
    provider = FakeProvider()
    agent = AccountingAgent(provider)

    agent.knowledge_base.add(
        "fatura", "Fatura kaydi nedir?", "Ornek cevap", "Ornek kaynak"
    )
    assert agent.ask("  fatura kaydi NEDIR? ") == "Ornek cevap\n\nKaynak: Ornek kaynak"

    answer = agent.ask("Fatura tutari nasil hesaplanir?")
    assert answer == "KAYNAKLI ARASTIRMA"
    assert "Fatura tutari nasil hesaplanir?" in provider.prompt
    assert date.today().isoformat() in provider.prompt
    assert str(date.today().year - 2) in provider.prompt

    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    memory_file = workspace / f"corrections_{uuid4().hex}.json"
    try:
        agent.learning_memory = LearningMemory(memory_file)
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


if __name__ == "__main__":
    test_accounting()
