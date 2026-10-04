import os

# Save and clear API key
api_key = os.environ.get('NGC_API_KEY')
print(f'Original key: {api_key[:20]}...' if api_key else 'No key')
os.environ['NGC_API_KEY'] = ''
print(f'New key: {os.environ.get("NGC_API_KEY", "(empty)")}')

# Now test
from core.ai.provider_factory import build_provider
from config.config_manager import ConfigManager

config = ConfigManager()
provider = build_provider(config)

print('\n--- Testing with empty API key ---')
answer = provider.ask('Merhaba')
print(f'Answer: {answer}')

# Restore
os.environ['NGC_API_KEY'] = api_key