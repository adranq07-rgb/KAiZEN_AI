import json
with open("config/Kaizen.json", "r", encoding="utf-8") as f:
    d = json.load(f)
print(json.dumps(d.get("model", {}), indent=2))