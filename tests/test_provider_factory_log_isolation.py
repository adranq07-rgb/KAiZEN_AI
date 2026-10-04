"""UAT bulgusu (2026-09-24, tools/research_uat.py Aşama K -- KaizenBrain shadow A/B testi
sırasında bulundu): `core/ai/provider_factory.py::build_provider()` eskiden `log_dir`
parametresi HİÇ ALMIYORDU -- bu yüzden `HermesProvider()` -> `HermesBridge()` HER ZAMAN
gerçek `logs/kaizen.log`'a yazıyordu. İzole/geçici bir sağlayıcı zinciri kurmak isteyen
HERHANGİ bir çağıran (test veya UAT script'i) bunu FARK ETMEDEN `data/`/`logs/` SHA
bütünlüğünü bozuyordu (madde 23 ihlali) -- reproducer script ile `/tmp/repro_provider_log_leak.py`
üzerinden kanıtlandı (gerçek logs/kaizen.log dosyasının hash'i değişti).

Düzeltme SADECE EKLEYİCİ: `build_provider(config, log_dir=None)` -- varsayılan `None`
MEVCUT davranışı (gerçek `logs/`) BİREBİR korur; `core/engine.py::KaizenEngine` (gerçek
prodüksiyon kullanımı) bu parametreyi hiç vermez, yani gerçek kullanıcı çalıştırması bu
değişiklikten ETKİLENMEZ."""
import tempfile
from pathlib import Path

from config.config_manager import ConfigManager
from core.ai.hermes_provider import HermesProvider
from core.ai.provider_factory import build_provider, _make


class _FakeConfig:
    """ConfigManager'ın gerçek dosyasına bağımlı olmadan `model.provider`/`model.fallback`
    seçimini test etmek için minimal sahte config (gerçek config/Kaizen.json'a hiç dokunmaz)."""

    def __init__(self, provider="hermes", fallback=None):
        self._provider = provider
        self._fallback = fallback if fallback is not None else ["offline"]

    def get(self, section, key, default=None):
        if section == "model" and key == "provider":
            return self._provider
        if section == "model" and key == "fallback":
            return self._fallback
        if section == "model" and key == "local":
            return {}
        return default

    def cloud_allowed(self):
        return True


def test_hermes_provider_accepts_log_dir_and_isolates_real_logs():
    """madde 23: `log_dir` verilirse HermesProvider/HermesBridge gerçek `logs/kaizen.log`'a
    HİÇ dokunmamalı -- yalnızca verilen izole dizine yazmalı."""
    with tempfile.TemporaryDirectory() as tmp:
        provider = HermesProvider(log_dir=tmp)
        assert str(provider.hermes.logger.log_dir) == tmp
        assert provider.hermes.logger.log_file == Path(tmp) / "kaizen.log"
    print("KAIZEN HERMESPROVIDER log_dir IZOLASYONU TESTI: BASARILI")


def test_hermes_provider_default_log_dir_unchanged_backward_compat():
    """madde 23 düzeltmesinin GERİYE DÖNÜK UYUMLULUK kanıtı: `log_dir` hiç verilmezse
    (mevcut TÜM üretim çağrıları -- core/engine.py dahil) davranış BİREBİR eskisi gibi
    kalır: gerçek proje `logs/` dizinine çözülür. Bu test hiçbir dosyaya YAZMAZ (yalnız
    `KaizenLogger.__init__`'in zaten var olan `logs/` üzerinde no-op `mkdir(exist_ok=True)`
    çağrısı çalışır), bu yüzden data/knowledge/memory/logs SHA bütünlüğünü bozmaz."""
    provider = HermesProvider()
    real_logs_dir = Path(__file__).resolve().parent.parent / "logs"
    assert provider.hermes.logger.log_dir == real_logs_dir
    print("KAIZEN HERMESPROVIDER log_dir VARSAYILAN (GERIYE DONUK UYUMLU) TESTI: BASARILI")


def test_build_provider_threads_log_dir_to_hermes():
    """`build_provider(config, log_dir=...)` -- ana sağlayıcı 'hermes' olduğunda
    `log_dir`'in gerçekten `HermesProvider`'a kadar ULAŞTIĞINI doğrular (madde 61: bu
    testte yeni bir sağlayıcı-seçim mantığı YAZILMAZ, yalnızca zaten var olan `_make`/
    `build_provider` GERÇEK config nesnesiyle çağrılır)."""
    config = _FakeConfig(provider="hermes", fallback=["offline"])
    with tempfile.TemporaryDirectory() as tmp:
        chain = build_provider(config, log_dir=tmp)
        # provider="hermes" + fallback=["offline"] -> FallbackProvider([HermesProvider, OfflineProvider])
        hermes_provider = chain.providers[0]
        assert isinstance(hermes_provider, HermesProvider)
        assert str(hermes_provider.hermes.logger.log_dir) == tmp
    print("KAIZEN BUILD_PROVIDER log_dir ZINCIRE ULASMA TESTI: BASARILI")


def test_build_provider_without_log_dir_still_constructs_chain():
    """`build_provider(config)` (log_dir hiç verilmeden) HÂLÂ eskisi gibi çalışır --
    yalnızca sağlayıcı zincirinin KURULABİLDİĞİ doğrulanır (gerçek Hermes CLI/ağ çağrısı
    YAPILMAZ, yalnız nesne inşası test edilir; core/engine.py'nin gerçek çağrısıyla AYNI
    imza)."""
    config = _FakeConfig(provider="hermes", fallback=["offline"])
    chain = build_provider(config)
    assert chain is not None
    print("KAIZEN BUILD_PROVIDER log_dir SIZ (VARSAYILAN IMZA) TESTI: BASARILI")


def test_make_offline_and_local_ignore_log_dir_harmlessly():
    """`_make()` 'offline'/'local' sağlayıcılar için `log_dir`'i sessizce YOK SAYAR (yalnız
    'hermes' bu parametreyi kullanır) -- bu, hatasız/çökmesiz olmalı."""
    config = _FakeConfig()
    offline = _make("offline", config, log_dir="/tmp/should-be-ignored")
    local = _make("local", config, log_dir="/tmp/should-be-ignored")
    assert offline is not None
    assert local is not None
    print("KAIZEN _MAKE OFFLINE/LOCAL log_dir YOKSAYMA TESTI: BASARILI")


if __name__ == "__main__":
    test_hermes_provider_accepts_log_dir_and_isolates_real_logs()
    test_hermes_provider_default_log_dir_unchanged_backward_compat()
    test_build_provider_threads_log_dir_to_hermes()
    test_build_provider_without_log_dir_still_constructs_chain()
    test_make_offline_and_local_ignore_log_dir_harmlessly()
