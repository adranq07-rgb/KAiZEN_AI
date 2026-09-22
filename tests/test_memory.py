from pathlib import Path

from accounting.learning_memory import LearningMemory
from memory.memory_manager import MemoryManager


def test_memory():
    test_root = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    test_root.mkdir(parents=True, exist_ok=True)
    memory_file = test_root / "kaizen_test_memory.json"
    learning_file = test_root / "kaizen_test_learning.json"
    assert not memory_file.exists() and not learning_file.exists()

    try:
        memory = MemoryManager(memory_file)
        memory.remember("tercih", "yerel")
        assert MemoryManager(memory_file).recall("tercih") == "yerel"

        memory_file.write_text("{bozuk", encoding="utf-8")
        try:
            MemoryManager(memory_file)
        except ValueError:
            pass
        else:
            raise AssertionError("Bozuk hafiza sessizce bos kabul edildi")

        learning_file.write_text("{bozuk", encoding="utf-8")
        try:
            LearningMemory(learning_file)
        except ValueError:
            pass
        else:
            raise AssertionError("Bozuk ogrenme dosyasi sessizce bos kabul edildi")
    finally:
        memory_file.unlink(missing_ok=True)
        learning_file.unlink(missing_ok=True)

    print("KAIZEN HAFIZA TESTI: BASARILI")


if __name__ == "__main__":
    test_memory()
