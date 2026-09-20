from core.logger import KazenLogger


def test_logger():
    logger = KazenLogger()

    logger.info("Otomatik logger testi")

    assert logger.log_file.exists()

    content = logger.log_file.read_text(encoding="utf-8")

    assert "Otomatik logger testi" in content

    print("KAZEN LOGGER TEST: BASARILI")


if __name__ == "__main__":
    test_logger()