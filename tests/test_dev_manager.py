from dev.dev_manager import DevManager


def test_dev_manager():
    dev = DevManager()

    assert dev.copy_for_testing("../AGENTS.md")[0] is False
    assert dev.promote_to_prod("../core/engine.py", "dev/test_prod.py", approved=True)[0] is False
    assert dev.promote_to_prod("engine.py", "../outside.py", approved=True)[0] is False
    assert dev.clear_workspace()[0] is False

    success, target = dev.copy_for_testing("core/engine.py")

    assert success is True
    assert dev.workspace.exists()
    assert (dev.workspace / "engine.py").exists()

    original = dev.project_dir / "core" / "engine.py"
    dev_copy = dev.workspace / "engine.py"

    assert original.read_bytes() == dev_copy.read_bytes()

    # Onaysiz PROD aktarimi engellenmeli.
    success, message = dev.promote_to_prod(
        "engine.py",
        "dev/test_prod.py",
        approved=False
    )

    assert success is False

    # Onayli aktarim calismali.
    success, target = dev.promote_to_prod(
        "engine.py",
        "dev/test_prod.py",
        approved=True
    )

    assert success is True

    test_prod = dev.project_dir / "dev" / "test_prod.py"
    assert test_prod.exists()

    # Test dosyasini temizle.
    test_prod.unlink()

    print("KAIZEN DEV GUVENLIK TESTI: BASARILI")


if __name__ == "__main__":
    test_dev_manager()
