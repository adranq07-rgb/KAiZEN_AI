from core.logger import KaizenLogger


def test_logger():
    logger = KaizenLogger()

    logger.info("Otomatik logger testi")

    assert logger.log_file.exists()

    content = logger.log_file.read_text(encoding="utf-8")

    assert "Otomatik logger testi" in content

    print("KAIZEN LOGGER TEST: BASARILI")


if __name__ == "__main__":
    test_logger()
