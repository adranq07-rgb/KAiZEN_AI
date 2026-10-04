from core.ai.provider_factory import build_provider
from config.config_manager import ConfigManager

config = ConfigManager()
provider = build_provider(config)

# Check providers
if hasattr(provider, 'providers'):
    for i, p in enumerate(provider.providers):
        print(f'Provider {i}: {type(p).__name__} - model: {getattr(p, "model_name", "N/A")} - base_url: {getattr(p, "base_url", "N/A")}')
        print(f'  is_ready: {p.is_ready()}')

# Test direct ask
print("\n--- Testing direct Nemotron call ---")
answer = provider.ask("KDV nedir? Kısaca açıkla.")
print(f"Answer: {answer}")