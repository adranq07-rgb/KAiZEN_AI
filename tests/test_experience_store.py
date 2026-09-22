from pathlib import Path

from memory.experience_store import ExperienceStore


def test_experience_store():
    test_dir = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "kaizen_test_experiences_v2.sqlite3"
    assert not test_file.exists()

    try:
        store = ExperienceStore(test_file)
        record = store.add(
            kind="source",
            provider="hermes",
            status="success",
            payload={"title": "Örnek"},
            source_refs=[{"url": "https://example.com"}],
        )
        assert ExperienceStore(test_file).get(record["id"]) == record
        assert store.get("missing") is None

        try:
            store.add("unknown", "hermes", "success", {})
        except ValueError:
            pass
        else:
            raise AssertionError("Bilinmeyen kayit turu kabul edildi")
    finally:
        test_file.unlink(missing_ok=True)

    print("KAIZEN GOREV KAYDI TESTI: BASARILI")


if __name__ == "__main__":
    test_experience_store()
