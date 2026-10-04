from core.engine import KaizenEngine

kaizen = KaizenEngine()
print('Kaizen Engine initialized')

print("\n--- Test: KDV question ---")
answer = kaizen.cevap_ver('KDV nedir? Kısaca açıkla.')
print(f"Answer: {answer}")

kaizen.shutdown()