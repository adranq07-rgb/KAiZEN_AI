import json
import urllib.request
import os

api_key = os.environ.get("NGC_API_KEY")
print(f"API Key: {api_key[:20]}...")

payload = json.dumps({
    "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "stream": False,
    "temperature": 0.2,
    "messages": [
        {"role": "system", "content": "Sen Kaizen AI'sın: Türkçe konuşan, kaynağa dayalı çalışan bir muhasebe ve mali müşavirlik yardımcısısın. Tutar, oran, hesap kodu, mevzuat veya kaynak uydurma; bilmiyorsan bilmediğini söyle."},
        {"role": "user", "content": "KDV nedir? Kısaca açıkla."}
    ],
}).encode("utf-8")

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

request = urllib.request.Request("https://integrate.api.nvidia.com/v1/chat/completions", data=payload, headers=headers)

print("Sending request...")
try:
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
        print(f"Response: {data}")
        print(f"Answer: {data['choices'][0]['message']['content'].strip()}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")