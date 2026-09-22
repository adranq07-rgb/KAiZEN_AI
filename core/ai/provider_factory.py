from core.ai.fallback_provider import FallbackProvider
from core.ai.hermes_provider import HermesProvider
from core.ai.local_provider import LocalProvider
from core.ai.offline_provider import OfflineProvider


def _make(name, config):
    if name == "hermes":
        return HermesProvider()
    if name == "local":
        settings = config.get("model", "local", {}) or {}
        return LocalProvider(
            base_url=settings.get("base_url", "http://localhost:11434/v1"),
            model_name=settings.get("model_name", ""),
            timeout=settings.get("timeout", 180),
            cloud_allowed=config.cloud_allowed(),
        )
    if name == "offline":
        return OfflineProvider()
    raise ValueError(f"Bilinmeyen sağlayıcı: {name} (hermes, local veya offline olmalı)")


def build_provider(config):
    """config/Kaizen.json'a göre sağlayıcı zincirini kurar.

    model.provider  : ana sağlayıcı (hermes | local | offline)
    model.fallback  : ana sağlayıcı çalışmazsa sırayla denenecekler (varsayılan: ["offline"])
    """
    primary = config.get("model", "provider", "hermes")
    fallbacks = config.get("model", "fallback", ["offline"]) or []
    names = [primary] + [n for n in fallbacks if n != primary]
    chain = [_make(name, config) for name in names]
    return chain[0] if len(chain) == 1 else FallbackProvider(chain)
