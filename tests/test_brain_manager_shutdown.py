"""`memory/brain_manager.py::BrainManager` deneyim hafızası (Cognee köprüsü) arka plan
worker lifecycle testleri.

BULGU (2026-09-25, kullanıcının ÜÇÜNCÜ gerçek Windows UAT koşusundan ÖNCEKİ, ikinci koşu
sonrası bulduğu gerçek hata): `tools/research_uat.py::stage_kaizenbrain_shadow` KaizenBrain
ON kolunu (`_run_with_timeout(brain_on.answer, ...)`) çalıştırdıktan hemen sonra, izole
`tempfile.TemporaryDirectory()` bloğu kapanıp geçici `logs/` dizini SİLİNİYORDU -- ama
`brain_on.answer()` içeride `self.brain.remember_experience(...)` (varsayılan
`background=True`) çağırdığı için bu iş bir arka plan kuyruğuna ekleniyor ve GERÇEKTEN
işlenmesi ayrı bir worker thread'e (`BrainManager._experience_worker_loop`) bırakılıyordu.
Bu worker, tempdir silindikten SONRA `_record_experience_write()` içinden
`self.logger.warning(...)` (ya da `.error(...)`) çağırdığında, `core/logger.py::KaizenLogger`
artık var olmayan bir dizine `open(..., "a")` ile yazmaya çalışıyor ve `FileNotFoundError`
fırlatıyordu -- hatta bu ikinci kez de oluyordu, çünkü `except Exception` bloğunun KENDİSİ
de `self.logger.error(...)` çağırıyor, o da aynı sebeple patlıyordu (uncaught, worker thread
sessizce ölüyordu).

Kök neden: `BrainManager`'ın arka plan worker'ları için hiçbir KONTROLLÜ KAPATMA (shutdown)
mekanizması yoktu -- worker'lar (daemon thread olsalar da) sonsuza kadar yaşıyordu ve
kuyruktaki/işlenmekte olan iş bitene kadar (ya da hiç bitmeyene kadar) çağıranın onları
beklemesi/durdurması için hiçbir API yoktu.

Bu dosyadaki testler REPRODUCER + REGRESYONDUR: `BrainManager.shutdown()` eklenmeden önce
(eski kod), `test_brain_manager_shutdown_stops_worker_before_late_log_access` `hasattr`
kontrolünde AÇIKÇA başarısız olur (bkz. testin docstring'i). `shutdown()` eklendikten sonra
tüm testler geçer.
"""
import shutil
import tempfile
import threading
from pathlib import Path

from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore


class _GatedExperienceDouble:
    """`CogneeMemory.remember()`'ın senkron arayüzünü taklit eder ama DETERMİNİSTİK bir
    kontrol noktası sağlar: `remember()` çağrıldığı ANDA `started` event'ini set eder (böylece
    test ana iş parçacığı işin GERÇEKTEN worker tarafından alınıp işlenmeye başladığını kör bir
    `time.sleep` yerine kesin olarak bilir), sonra `release` event'i set edilene kadar bloke
    olur (böylece test, log dizinini TAM OLARAK worker mid-flight'ken -- gerçek PC'deki en kötü
    zamanlama senaryosunu birebir yeniden üreterek -- silebilir). `ok=False` döner ki
    `BrainManager._record_experience_write` gerçek koddaki `self.logger.warning(...)` dalına
    girsin (tam olarak gerçek PC'deki hatayı tetikleyen kod yolu)."""

    def __init__(self, started_event, release_event):
        self.started_event = started_event
        self.release_event = release_event
        self.calls = 0

    def remember(self, text, dataset=None):
        self.calls += 1
        self.started_event.set()
        self.release_event.wait(timeout=5)
        return {"ok": False, "status": "failed", "dataset": dataset, "error": "test-forced-not-ok"}

    def recall(self, query, dataset=None, top_k=None):
        return {"ok": False, "results": []}


def _make_brain_manager(tmp_dir, experience):
    learning_store = LearningStore(db_path=Path(tmp_dir) / "kaizen_learning.sqlite3")
    return BrainManager(
        learning_store=learning_store, site_store=None, facts=None, cards=None,
        exam_candidates_path=Path(tmp_dir) / "auto_exam_candidates.jsonl",
        experience_memory=experience, log_dir=str(Path(tmp_dir) / "logs"),
    )


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_brain_manager_shutdown_stops_worker_before_late_log_access():
    """ANA REPRODUCER + REGRESYON. ESKİ KODDA (henüz `BrainManager.shutdown()` yokken) bu test
    `hasattr(bm, "shutdown")` satırında AÇIKÇA ve okunabilir biçimde BAŞARISIZ olur -- bu,
    "worker'ları kontrollü durduracak hiçbir API yok" kök nedeninin doğrudan kanıtıdır.
    YENİ KODDA: worker `experience.remember()` içinde GERÇEKTEN bloke olmuşken (mid-flight)
    log dizini silinir -- gerçek PC senaryosunun BİREBİR simülasyonu -- sonra `shutdown()`
    çağrılır. `shutdown()`'ın DÖNMESİ İÇİN worker'ın GERÇEKTEN bitmesi (thread.join başarılı)
    gerekir; `shutdown()` döndükten sonra worker'ın `is_alive()==False` olduğu doğrulanır
    (yani hiçbir worker artık logger/storage'a dokunamaz) VE worker'ın (artık dizin yokken bile
    -- logger robustness düzeltmesi sayesinde) çökmeden `experience_stats()['failed']`e
    doğru şekilde işlediği doğrulanır."""
    tmp = tempfile.mkdtemp(prefix="kaizen_brainmanager_shutdown_test_")
    try:
        started = threading.Event()
        release = threading.Event()
        experience = _GatedExperienceDouble(started, release)
        bm = _make_brain_manager(tmp, experience)

        bm.remember_experience("test sorusu", "test cevabı")  # background=True (varsayılan)
        assert started.wait(timeout=5), "worker beklenen sürede işi almadı -- test kurulumu bozuk"

        # Gerçek PC'deki en kötü zamanlama: worker HÂLÂ `.remember()` içindeyken (mid-flight)
        # log dizini (ve tüm geçici depolama) siliniyor.
        shutil.rmtree(tmp, ignore_errors=True)
        assert not Path(tmp).exists()

        release.set()  # worker'ın `.remember()` çağrısı ŞİMDİ döner -- dizin ZATEN gitmiş.

        assert hasattr(bm, "shutdown"), (
            "BrainManager.shutdown() eksik -- arka plan worker'larının lifecycle'ını "
            "KONTROLLÜ olarak sonlandıracak hiçbir API yok (kök neden)."
        )

        threads_before = list(bm._experience_threads)
        assert threads_before, "test kurulumu hatası: hiç worker thread başlamamış görünüyor"

        completed = bm.shutdown(timeout=5.0)

        assert completed is True, "shutdown() worker'ların gerçekten bittiğini timeout içinde doğrulayamadı"
        assert all(not t.is_alive() for t in threads_before), (
            "shutdown() döndü ama en az bir worker thread HÂLÂ canlı -- 'shutdown sonrası "
            "hiçbir worker logger/storage kullanmaz' garantisi ihlal edildi"
        )
        assert bm._experience_threads == []

        stats = bm.experience_stats()
        assert stats["failed"] == 1, (
            f"worker, log dizini silindikten sonra bile çökmeden 'failed' olarak "
            f"işleyebilmeliydi (logger robustness) -- stats={stats}"
        )

        # Shutdown SONRASI gelen geç bir çağrı: sessizce reddedilmeli, yeni worker/log erişimi
        # OLUŞTURMAMALI.
        bm.remember_experience("geç gelen soru", "geç gelen cevap")
        stats_after = bm.experience_stats()
        assert stats_after["dropped"] >= 1, "shutdown sonrası yeni iş sessizce KABUL EDİLMİŞ olabilir"
        assert bm._experience_threads == [], "shutdown sonrası YENİ bir worker thread başlatılmış"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("KAIZEN BRAINMANAGER SHUTDOWN: MID-FLIGHT WORKER + SILINEN LOG DIZINI REPRODUCER TESTI: BASARILI")


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_brain_manager_shutdown_is_idempotent():
    """İki kez `shutdown()` çağrılması güvenli olmalı -- ikinci çağrı anında no-op dönmeli,
    ne bir istisna fırlatmalı ne de tekrar drain/join denemeli."""
    tmp = tempfile.mkdtemp(prefix="kaizen_brainmanager_shutdown_idempotent_")
    try:
        started = threading.Event()
        release = threading.Event()
        release.set()  # worker hiç bloke olmasın, hemen dönsün
        experience = _GatedExperienceDouble(started, release)
        bm = _make_brain_manager(tmp, experience)

        bm.remember_experience("soru", "cevap")
        assert started.wait(timeout=5)

        first = bm.shutdown(timeout=5.0)
        second = bm.shutdown(timeout=5.0)
        third = bm.shutdown()  # varsayılan timeout ile de idempotent olmalı

        assert first is True
        assert second is True
        assert third is True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("KAIZEN BRAINMANAGER SHUTDOWN: IKI KEZ CAGRILMA (IDEMPOTENT) TESTI: BASARILI")


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_brain_manager_shutdown_accounts_for_all_queued_work_within_bounded_time():
    """'Kuyruktaki işlerin politikası açık olmalı: ya bounded süre içinde flush, ya güvenli
    drop' -- bu test, kuyruğa kapasiteyi aşacak kadar (queue maxsize=20) iş konulduğunda
    `shutdown(timeout=...)`'un HER ZAMAN bounded sürede DÖNDÜĞÜNÜ (asla sonsuza kadar
    beklemediğini) ve enqueue edilen HİÇBİR işin sessizce KAYBOLMADIĞINI (written+failed+
    dropped+hâlâ kuyrukta toplamının tutarlı kaldığını) doğrular."""
    import time

    tmp = tempfile.mkdtemp(prefix="kaizen_brainmanager_shutdown_bounded_")
    try:
        class _SlowExperienceDouble:
            def __init__(self):
                self.calls = 0

            def remember(self, text, dataset=None):
                self.calls += 1
                time.sleep(0.5)  # her yazım "yavaş" -- kısa timeout'ta hepsi bitemez
                return {"ok": True, "status": "completed", "dataset": dataset, "error": None}

            def recall(self, query, dataset=None, top_k=None):
                return {"ok": False, "results": []}

        experience = _SlowExperienceDouble()
        bm = _make_brain_manager(tmp, experience)

        total_jobs = 8
        for i in range(total_jobs):
            bm.remember_experience(f"soru {i}", f"cevap {i}")

        threads_before = list(bm._experience_threads)
        assert threads_before, "test kurulumu hatası: hiç worker thread başlamamış görünüyor"

        t0 = time.monotonic()
        completed = bm.shutdown(timeout=1.0)  # 8 iş * 0.5s / 2 worker ~= 2s > 1.0s bütçe -- hepsi bitemez
        elapsed = time.monotonic() - t0

        # ASIL garanti: `shutdown()` ÇAĞRISININ KENDİSİ, kuyrukta hâlâ iş olsa bile bounded
        # sürede döner -- sonsuza kadar (ya da tüm 8 iş bitene ~4s kadar) BLOKLANIP KALMAZ.
        assert elapsed < 3.0, f"shutdown() bounded timeout'a rağmen çok uzun sürdü: {elapsed:.2f}s"
        assert isinstance(completed, bool)

        # `completed` False olabilir -- bir worker, timeout anında tam bir işi işlemekte
        # (mid-flight) olabilir; bu GÜVENLİDİR (madde: "kaybolan" değil, yalnızca GECİKEN bir
        # iştir) ama `shutdown()` döndüğü ANDA henüz `written`/`failed`/`dropped` sayaçlarından
        # HİÇBİRİNE işlenmemiş olabilir (worker hâlâ o işi bitirmeye çalışıyordur). Testin
        # "hiçbir iş sessizce/kalıcı olarak kaybolmuyor" iddiasını doğrulamak için, ELİMİZDEKİ
        # thread referanslarının (`threads_before`) GERÇEKTEN bitmesini (varsa mid-flight işi
        # doğal olarak tamamlayıp sentinel'i alıp çıkmasını) kısa bir SÜRE daha bekleriz --
        # bu, `shutdown()` çağrısının KENDİSİNİ bloklamaz, yalnızca bu testin doğrulamasını.
        for t in threads_before:
            t.join(timeout=3.0)

        stats = bm.experience_stats()
        accounted = stats["written"] + stats["failed"] + stats["dropped"] + stats["queued"]
        assert accounted == total_jobs, (
            f"enqueue edilen {total_jobs} işten bazıları HİÇBİR ZAMAN hesaba katılmadan "
            f"(gerçekten) kayboldu: {stats}"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("KAIZEN BRAINMANAGER SHUTDOWN: BOUNDED FLUSH/DROP POLITIKASI (HICBIR IS KAYBOLMAZ) TESTI: BASARILI")


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_brain_manager_shutdown_never_raises_when_storage_and_logger_both_fail():
    """'shutdown sırasında storage/Cognee unavailable olsa bile exception dışarı kaçmamalı.'
    `experience.remember()` istisna fırlatsın VE log dizini de silinmiş olsun -- `shutdown()`
    yine de hiçbir istisna sızdırmadan dönmeli."""
    tmp = tempfile.mkdtemp(prefix="kaizen_brainmanager_shutdown_double_failure_")
    try:
        started = threading.Event()

        class _ExplodingExperienceDouble:
            def remember(self, text, dataset=None):
                started.set()
                raise RuntimeError("test: depolama katmanı beklenmedik şekilde çöktü")

            def recall(self, query, dataset=None, top_k=None):
                raise RuntimeError("test: depolama katmanı beklenmedik şekilde çöktü")

        bm = _make_brain_manager(tmp, _ExplodingExperienceDouble())
        bm.remember_experience("soru", "cevap")
        assert started.wait(timeout=5)

        shutil.rmtree(tmp, ignore_errors=True)  # logger'ın kendisi de artık yazamaz

        try:
            completed = bm.shutdown(timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"shutdown() istisna sızdırdı (ASLA olmamalı): {exc!r}") from exc

        assert isinstance(completed, bool)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("KAIZEN BRAINMANAGER SHUTDOWN: STORAGE+LOGGER IKISI DE COKERKEN ISTISNA SIZDIRMAZ TESTI: BASARILI")


if __name__ == "__main__":
    test_brain_manager_shutdown_stops_worker_before_late_log_access()
    test_brain_manager_shutdown_is_idempotent()
    test_brain_manager_shutdown_accounts_for_all_queued_work_within_bounded_time()
    test_brain_manager_shutdown_never_raises_when_storage_and_logger_both_fail()
