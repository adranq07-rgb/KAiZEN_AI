from core.engine import KaizenEngine

kaizen = KaizenEngine()
print('Kaizen Engine initialized')

# Test provider chain
providers = kaizen.provider_manager.provider.providers
print(f'Total providers: {len(providers)}')
for i, p in enumerate(providers):
    print(f'  Provider {i}: {type(p).__name__} - model: {getattr(p, "model_name", "N/A")} - base_url: {getattr(p, "base_url", "N/A")}')

# Test Nemotron directly
print('\n--- Direct Nemotron test ---')
nemotron = providers[0]
print(f'is_ready: {nemotron.is_ready()}')
answer = nemotron.ask('KDV nedir? Kısaca açıkla.')
print(f'Nemotron answer: {answer[:200]}...')

kaizen.shutdown()