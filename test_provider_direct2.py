from core.ai.provider_factory import build_provider
from config.config_manager import ConfigManager

config = ConfigManager()
provider = build_provider(config)

# Test direct ask
print("\n--- Testing direct Nemotron call ---")
answer = provider.ask("KDV nedir? Kısaca açıkla.")
print(f"Answer: {answer}")