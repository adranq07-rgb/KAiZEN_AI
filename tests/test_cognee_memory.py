import enum
from types import SimpleNamespace

from memory.cognee_memory import CogneeMemory


class _FakeCognee:
    """Gerçek cognee 1.6.0 imzalarını taklit eder; Ollama/cognee kurulu olmadan test için."""

    SearchType = enum.Enum("SearchType", {"CHUNKS": "CHUNKS", "GRAPH_COMPLETION": "GRAPH_COMPLETION"})

    def __init__(self, recall_items=None):
        self.calls = []
        self.recall_items = recall_items or []

    async def remember(self, data, dataset_name="main_dataset", *, self_improvement=True, raise_on_error=True):
        self.calls.append(("remember", data, dataset_name, self_improvement, raise_on_error))
        return SimpleNamespace(status="completed", dataset_name=dataset_name, error=None)

    async def recall(self, query_text, query_type=None, *, datasets=None, top_k=15):
        self.calls.append(("recall", query_text, query_type, datasets, top_k))
        return self.recall_items

    async def forget(self, *, dataset=None):
        self.calls.append(("forget", dataset))
        return {"datasets_removed": 1}


def _memory(fake=None, **settings):
    memory = CogneeMemory(settings={"enabled": True, **settings}, storage_dir="unused")
    memory._cognee = fake
    return memory


def test_cognee_memory():
    # Kapalıyken hiçbir şey yüklenmez, hata fırlatılmaz.
    closed = CogneeMemory(settings={"enabled": False}, storage_dir="unused")
    assert closed.remember("x")["ok"] is False
    assert closed.recall("x")["results"] == []
    assert closed._cognee is None

    # Uzak uç nokta: hafıza buluta gönderilmez.
    remote = CogneeMemory(settings={"enabled": True, "llm_endpoint": "https://inference-api.nousresearch.com"},
                          storage_dir="unused")
    assert remote.is_ready() is False
    assert "buluta" in remote.remember("x")["error"]

    # Ortam: docs.cognee.ai/guides/local-setup ile birebir.
    env = _memory().build_env()
    assert env["LLM_PROVIDER"] == "ollama" and env["EMBEDDING_PROVIDER"] == "ollama"
    assert env["LLM_ENDPOINT"] == "http://localhost:11434"  # /v1 olmamalı
    assert env["EMBEDDING_ENDPOINT"].endswith("/api/embed")
    assert env["LLM_API_KEY"] and env["TELEMETRY_DISABLED"] == "1"

    fake = _FakeCognee(recall_items=[
        SimpleNamespace(source="graph", text="KDV oranı kaynağı: GİB"),
        SimpleNamespace(source="session", answer="Önceki cevap"),
    ])
    memory = _memory(fake)
    assert memory.remember("   ")["ok"] is False
    stored = memory.remember("Müşteri X'in vergi dairesi Kadıköy.")
    assert stored == {"ok": True, "status": "completed", "dataset": "kaizen", "error": None}
    assert fake.calls[-1][3] is False and fake.calls[-1][4] is False

    found = memory.recall("vergi dairesi")
    assert found["ok"] is True
    assert [r["text"] for r in found["results"]] == ["KDV oranı kaynağı: GİB", "Önceki cevap"]
    assert fake.calls[-1][2] == _FakeCognee.SearchType.CHUNKS
    assert fake.calls[-1][3] == ["kaizen"]

    # Sistem işareti veri sayılmaz.
    warming = _memory(_FakeCognee(recall_items=[SimpleNamespace(source="system", text="warming up")]))
    assert warming.recall("x")["ok"] is False

    # Silme onaysız yapılmaz.
    assert memory.forget()["ok"] is False
    assert not any(call[0] == "forget" for call in fake.calls)
    assert memory.forget(confirmed=True)["ok"] is True
    assert fake.calls[-1] == ("forget", "kaizen")

    # Ollama yoksa sağlık kontrolü açıkça başarısız olur.
    assert _memory(llm_endpoint="http://127.0.0.1:9").health(timeout=1)["ok"] is False

    print("KAIZEN COGNEE HAFIZA TESTI: BASARILI")


if __name__ == "__main__":
    test_cognee_memory()
