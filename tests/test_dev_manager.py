from dev.dev_manager import DevManager


def test_dev_manager():
    dev = DevManager()

    success, target = dev.copy_for_testing("core/engine.py")

    assert success is True
    assert dev.workspace.exists()
    assert (dev.workspace / "engine.py").exists()

    original = dev.project_dir / "core" / "engine.py"
    dev_copy = dev.workspace / "engine.py"

    assert original.read_bytes() == dev_copy.read_bytes()

    print("KAZEN DEV TEST: BASARILI")


if __name__ == "__main__":
    test_dev_manager()