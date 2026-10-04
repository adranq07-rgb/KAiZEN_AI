from core.engine import KaizenEngine

kaizen = KaizenEngine()
print('Kaizen Engine initialized')

# Test simple non-accounting question
print("\n--- Test 1: Simple greeting ---")
answer = kaizen.cevap_ver('Merhaba')
print(f"Answer: {answer}")

print("\n--- Test 2: Simple question ---")
answer = kaizen.cevap_ver('2+2 kaç eder?')
print(f"Answer: {answer}")

kaizen.shutdown()