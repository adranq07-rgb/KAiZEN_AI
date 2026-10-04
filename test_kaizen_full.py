from core.engine import KaizenEngine

kaizen = KaizenEngine()
print('Kaizen Engine initialized')
print(f'Provider type: {type(kaizen.provider_manager.provider).__name__}')

# Check the underlying providers
if hasattr(kaizen.provider_manager.provider, 'providers'):
    for i, p in enumerate(kaizen.provider_manager.provider.providers):
        print(f'Provider {i}: {type(p).__name__} - model: {getattr(p, "model_name", "N/A")} - base_url: {getattr(p, "base_url", "N/A")}')

answer = kaizen.cevap_ver('KDV nedir? Kısaca açıkla.')
print(f'Answer: {answer}')
kaizen.shutdown()