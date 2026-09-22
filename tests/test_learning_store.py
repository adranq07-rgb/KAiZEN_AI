from pathlib import Path
from uuid import uuid4

from memory.learning_store import LearningStore


def test_learning_store():
    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    db_path = workspace / f"learning_{uuid4().hex}.sqlite3"
    try:
        store = LearningStore(db_path)
        text = " ".join(f"kelime{i}" for i in range(30))
        first = store.add(domain="accounting", subject="A", source_path="a.pdf",
                          source_type="pdf_page", section="1", locator="sayfa 1", text=text)
        second = store.add(domain="accounting", subject="B", source_path="b.pdf",
                           source_type="pdf_page", section="2", locator="sayfa 2", text=text)
        assert first == second
        assert store.stats()["total"] == 1
        assert store.search("kelime10", domain="accounting")[0]["id"] == first
    finally:
        db_path.unlink(missing_ok=True)

    print("KAIZEN OGRENME BELLEGI TESTI: BASARILI")


if __name__ == "__main__":
    test_learning_store()
