import shutil
import tempfile
from pathlib import Path

from core.logger import KaizenLogger


def test_logger():
    # log_dir: gercek logs/kaizen.log yerine izole bir gecici klasor kullanilir; boylece
    # bu test gercek proje log dosyasina hicbir sey yazmaz.
    with tempfile.TemporaryDirectory() as log_dir:
        logger = KaizenLogger(log_dir=log_dir)

        logger.info("Otomatik logger testi")

        assert logger.log_file.exists()

        content = logger.log_file.read_text(encoding="utf-8")

        assert "Otomatik logger testi" in content

    print("KAIZEN LOGGER TEST: BASARILI")


def test_logger_does_not_raise_when_log_dir_removed():
    """SAĞLAMLIK (2026-09-25, gerçek PC UAT bulgusu): `BrainManager`'ın arka plan deneyim
    worker'ı, kendi geçici log dizini runtime sırasında silindiğinde `KaizenLogger`'ın
    çıplak `open(..., "a")` çağrısı yüzünden `FileNotFoundError` alıyor, hatta hata
    işleyicisinin kendisi de aynı şekilde ikinci kez patlıyordu. Bu, ASIL düzeltme değil
    (asıl düzeltme `BrainManager.shutdown()` -- worker'lar dizin silinmeden ÖNCE durdurulmalı),
    ama `KaizenLogger` genel olarak da loglama gibi best-effort bir yan işlemin çağıranı
    ASLA çökertmemesi gerektiğini garanti etmeli (log dizini prod'da da her an silinebilir:
    temizlik betiği, antivirüs, kullanıcı vb.). ESKİ kodda bu test `FileNotFoundError` ile
    BAŞARISIZ olur."""
    tmp = tempfile.mkdtemp(prefix="kaizen_logger_robustness_test_")
    try:
        log_dir = Path(tmp) / "logs"
        logger = KaizenLogger(log_dir=str(log_dir))
        assert log_dir.is_dir()

        shutil.rmtree(tmp, ignore_errors=True)
        assert not log_dir.exists()

        try:
            logger.warning("dizin silindikten sonra bir uyarı")
            logger.error("dizin silindikten sonra bir hata")
            logger.info("dizin silindikten sonra bir bilgi")
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(
                f"KaizenLogger, log dizini silindiğinde İSTİSNA fırlattı (asla fırlatmamalı): {exc!r}"
            ) from exc

        # Best-effort kendini onarma: dizin yeniden oluşturulabildiyse içerik de doğru olmalı.
        if log_dir.exists():
            content = (log_dir / "kaizen.log").read_text(encoding="utf-8")
            assert "dizin silindikten sonra bir bilgi" in content
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("KAIZEN LOGGER: LOG DIZINI RUNTIME SIRASINDA SILINDIGINDE ISTISNA FIRLATMIYOR TESTI: BASARILI")


if __name__ == "__main__":
    test_logger()
    test_logger_does_not_raise_when_log_dir_removed()
