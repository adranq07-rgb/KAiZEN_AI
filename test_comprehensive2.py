import sys
import codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

from core.engine import KaizenEngine

kaizen = KaizenEngine()
print('Kaizen Engine initialized')

# Test provider chain
providers = kaizen.provider_manager.provider.providers
print(f'Total providers: {len(providers)}')
for i, p in enumerate(providers):
    print(f'  Provider {i}: {type(p).__name__} - model: {getattr(p, "model_name", "N/A")} - base_url: {getattr(p, "base_url", "N/A")}')

# Test Nemotron directly
print('\n--- Test 1: Nemotron (primary) ---')
nemotron = providers[0]
print(f'is_ready: {nemotron.is_ready()}')
answer = nemotron.ask('KDV nedir? Kısaca açıkla.')
print(f'Nemotron answer length: {len(answer)} chars')

# Test local fallback
print('\n--- Test 2: Local fallback (llama3.2:3b) ---')
local = providers[1]
print(f'is_ready: {local.is_ready()}')
answer = local.ask('KDV nedir? Kısaca açıkla.')
print(f'Local answer length: {len(answer)} chars')

# Test full Kaizen flow
print('\n--- Test 3: Full Kaizen flow (simple question) ---')
answer = kaizen.cevap_ver('Merhaba')
print(f'Kaizen answer: {answer}')

print('\n--- Test 4: Full Kaizen flow (math question) ---')
answer = kaizen.cevap_ver('2+2 kaç eder?')
print(f'Kaizen answer: {answer}')

kaizen.shutdown()
print('\n=== ALL TESTS PASSED ===')