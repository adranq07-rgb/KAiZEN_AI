"""Testlerde paylaşılan sahte (fake/test double) nesneler.

`NullExperienceMemory`: `BrainManager`/`KaizenBrain`, deneyim hafızası (Cognee, Kademe 2)
enjekte edilmeden kurulduğunda varsayılan olarak GERÇEK bir `memory.cognee_memory.CogneeMemory()`
örneği oluşturur (bkz. memory/brain_manager.py). Bu, `cognee` paketi KURULU OLMAYAN bu bulut
ortamında zararsızdır (her çağrı hemen "ok": False döner, hiçbir ağ/disk işlemi yapılmaz) --
ama kullanıcının kendi bilgisayarında (`cognee` kurulu, `config/Kaizen.json` içinde
`memory.cognee.enabled: true`) AYNI testler GERÇEK Ollama'ya gerçek yazma/okuma çağrıları yapar
ve test verisini (ör. altın sınavdaki 70 soru-cevap, ya da "kırılma testi" gibi rastgele metinler)
kullanıcının KALICI kişisel hafızasına (`data/cognee/` altındaki "kaizen" veri kümesi) yazar.

Testler hiçbir zaman gerçek kalıcı hafızaya dokunmamalı -- bu yüzden `BrainManager`/`KaizenBrain`
kurulduğu HER test yerinde (deneyim hafızasının kendisini kasıtlı olarak test eden yerler hariç,
onlar kendi sahte nesnelerini kullanır) bu sınıf açıkça geçirilir.
"""


class NullExperienceMemory:
    """`CogneeMemory`'nin senkron arayüzünü (remember/recall) taklit eder ama HİÇBİR ZAMAN
    gerçek bir ağ/disk işlemi yapmaz -- yalnızca çağrıldığını (ve neyle çağrıldığını) kaydeder."""

    def __init__(self):
        self.remembered = []
        self.recalled = []

    def remember(self, text, dataset=None):
        self.remembered.append(text)
        return {"ok": True, "status": "completed", "dataset": dataset or "kaizen", "error": None}

    def recall(self, query, dataset=None, top_k=None):
        self.recalled.append(query)
        return {"ok": True, "results": []}
