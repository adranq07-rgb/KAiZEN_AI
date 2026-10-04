from core.ai.fallback_provider import FallbackProvider
from core.ai.hermes_provider import HermesProvider
from core.ai.local_provider import LocalProvider
from core.ai.offline_provider import OfflineProvider


def _make(name, config, log_dir=None):
    if name == "hermes":
        return HermesProvider(log_dir=log_dir)
    if name == "local":
        settings = config.get("model", "local", {}) or {}
        return LocalProvider(
            base_url=settings.get("base_url", "http://localhost:11434/v1"),
            model_name=settings.get("model_name", ""),
            timeout=settings.get("timeout", 180),
            cloud_allowed=config.cloud_allowed(),
        )
    if name == "nemotron":
        # Mevcut NVIDIA/Nemotron erişimi (OpenAI uyumlu uç nokta). Anahtar ASLA dosyaya yazılmaz:
        # yalnız `api_key_env` ile adı verilen ortam değişkeninden okunur. Yoksa is_ready()
        # false olur ve FallbackProvider zinciri (local -> offline) çalışmaya devam eder.
        import os
        settings = config.get("model", "nemotron", {}) or {}
        return LocalProvider(
            base_url=settings.get("base_url", "https://integrate.api.nvidia.com/v1"),
            model_name=settings.get("model_name", ""),
            timeout=settings.get("timeout", 120),
            cloud_allowed=config.cloud_allowed(),
            api_key=os.environ.get(settings.get("api_key_env", "NVIDIA_API_KEY")) or None,
        )
    if name == "offline":
        return OfflineProvider()
    raise ValueError(f"Bilinmeyen sağlayıcı: {name} (hermes, local, nemotron veya offline olmalı)")


def build_provider(config, log_dir=None):
    """config/Kaizen.json'a göre sağlayıcı zincirini kurar.

    model.provider  : ana sağlayıcı (hermes | local | offline)
    model.fallback  : ana sağlayıcı çalışmazsa sırayla denenecekler (varsayılan: ["offline"])

    `log_dir` (UAT bulgusu, 2026-09-24): İSTEĞE BAĞLI, varsayılanı `None` -- verilmezse
    MEVCUT davranış (gerçek `logs/kaizen.log`, bkz. core/logger.py::KaizenLogger) BİREBİR
    korunur; `core/engine.py::KaizenEngine` (gerçek prodüksiyon kullanımı) bu parametreyi
    HİÇ vermez, yani gerçek kullanıcı çalıştırması bu değişiklikten ETKİLENMEZ. Yalnızca
    izole/geçici bir sağlayıcı zinciri kurmak isteyen bir çağıran (test veya
    `tools/research_uat.py`) artık `logs/`'u kendi geçici dizinine yönlendirebilir."""
    primary = config.get("model", "provider", "hermes")
    fallbacks = config.get("model", "fallback", ["offline"]) or []
    names = [primary] + [n for n in fallbacks if n != primary]
    chain = [_make(name, config, log_dir=log_dir) for name in names]
    return chain[0] if len(chain) == 1 else FallbackProvider(chain)
