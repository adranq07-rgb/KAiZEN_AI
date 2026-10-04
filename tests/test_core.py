import hashlib
import tempfile
from pathlib import Path

from core.ai.offline_provider import OfflineProvider
from core.engine import KaizenEngine

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Kabul olcutu (kullanicinin istegi): testler calisirken bu gercek yollarin HICBIRINE
# yazilmamali. data/ ve logs/ dizinleri, memory/kaizen_memory.json bu yuzden burada
# once/sonra karsilastirilir.
_REAL_PATHS_TO_WATCH = [
    _PROJECT_ROOT / "data",
    _PROJECT_ROOT / "logs",
    _PROJECT_ROOT / "memory" / "kaizen_memory.json",
]


def _snapshot(paths):
    """Izlenen gercek dosya/dizinlerin icerik parmak izini (hash) cikarir.

    Var olmayan bir yol 'yok' (None) olarak kaydedilir; test sonunda hala 'yok'
    olmasi gerekir (testin onu yaratmis olmamasi lazim). Var olan bir dizin,
    icindeki her dosyanin yolu + icerik hash'i olarak kaydedilir; boylece yeni bir
    dosya eklenmesi de, var olan bir dosyanin icerigi degismesi de yakalanir.
    """
    snapshot = {}
    for base in paths:
        if not base.exists():
            snapshot[str(base)] = None
            continue
        if base.is_file():
            snapshot[str(base)] = hashlib.sha256(base.read_bytes()).hexdigest()
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                snapshot[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def test_core():
    before = _snapshot(_REAL_PATHS_TO_WATCH)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        log_dir = tmp_path / "logs"

        # provider=OfflineProvider(): build_provider() hic cagrilmaz -> gercek
        # Hermes/yerel model kurulumu (ag/soket) devreye girmez.
        kaizen = KaizenEngine(data_dir=data_dir, log_dir=log_dir, provider=OfflineProvider())

        assert kaizen.model_manager is not None
        assert kaizen.memory_manager is not None
        assert kaizen.tool_manager is not None
        assert kaizen.security_manager is not None

        assert kaizen.provider_manager is not None
        assert kaizen.provider_manager.provider is not None
        assert kaizen.provider_manager.provider.is_offline is True
        assert kaizen.accounting_agent is not None
        assert kaizen.cevap_ver("muhasebe: ") == "Kaizen: Muhasebe sorusu bos olamaz."

        kaizen.brain.answer = lambda message: f"BEYIN:{message}"

        assert kaizen.cevap_ver("Merhaba") == "BEYIN:Merhaba"
        assert kaizen.cevap_ver("muhasebe: Fatura kaydi nedir?") == "BEYIN:muhasebe: Fatura kaydi nedir?"

        # Izolasyonun SUSLU degil GERCEKTEN calistigini dogrula: motorun her kalici
        # deposu, verilen gecici klasordeki dosyalara yazmis olmali -- yoksa asagidaki
        # "gercek dosyalar degismedi" kontrolu hicbir sey ispatlamaz (yanlissiz-yesil olur).
        assert kaizen.learning_store.db_path == data_dir / "kaizen_learning.sqlite3"
        assert kaizen.learning_store.db_path.exists()
        assert kaizen.site_store.db_path == data_dir / "accounting_knowledge.sqlite3"
        assert kaizen.site_store.db_path.exists()
        assert kaizen.accounting_agent.learning_memory.file_path == data_dir / "accounting_learning.json"
        assert kaizen.accounting_agent.learning_memory.file_path.exists()
        assert kaizen.memory_manager.memory_file == data_dir / "kaizen_memory.json"
        assert kaizen.brain.brain.exam_candidates_path == data_dir / "auto_exam_candidates.jsonl"
        assert kaizen.logger.log_file == log_dir / "kaizen.log"
        assert kaizen.logger.log_file.exists()  # __init__ sonunda logger.info() cagrilir

    after = _snapshot(_REAL_PATHS_TO_WATCH)
    assert before == after, (
        "KABUL OLCUTU IHLALI: test calisirken projenin gercek data/, logs/ veya "
        "memory/kaizen_memory.json dosyalarindan biri degisti."
    )

    print("KAIZEN CORE TEST: BASARILI")


def test_core_default_paths_unchanged_when_no_override_given():
    """data_dir/log_dir/provider verilmezse (normal kullanim -- main.py, desktop_app.py)
    KaizenEngine'in eski davranisi birebir korunmali: gercek data/logs dizinleri ve
    config/Kaizen.json'dan secilen gercek provider. Bu test motoru GERCEK yollarla
    KURMAZ (bu dosyanin geri kalani gercek dosyalara dokunulmamasini garanti ediyor);
    yalnizca varsayilan degerlerin ne olacagini, motoru hic olusturmadan, statik olarak
    dogrular."""
    import inspect

    signature = inspect.signature(KaizenEngine.__init__)
    assert signature.parameters["data_dir"].default is None
    assert signature.parameters["log_dir"].default is None
    assert signature.parameters["provider"].default is None

    print("KAIZEN CORE VARSAYILAN YOL TESTI: BASARILI")


if __name__ == "__main__":
    test_core()
    test_core_default_paths_unchanged_when_no_override_given()
