from core.ai.provider_factory import build_provider
from config.config_manager import ConfigManager
import os

config = ConfigManager()
provider = build_provider(config)
print(f'Provider type: {type(provider).__name__}')
print(f'Provider chain: {[type(p).__name__ for p in getattr(provider, "providers", [provider])]}')

# Test Nemotron
print(f'NGC_API_KEY set: {bool(os.environ.get("NGC_API_KEY"))}')
print(f'NGC_API_KEY preview: {os.environ.get("NGC_API_KEY", "")[:20]}...')

# Test the actual call
print("\n--- Testing Nemotron call ---")
answer = provider.ask("KDV nedir? Kısaca açıkla.")
print(f"Answer: {answer}")