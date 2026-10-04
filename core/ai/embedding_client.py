"""KAIZEN — TAM ENTEGRASYON FAZI, Bölüm 2: bge-m3 embedding istemcisi.

Yalnız ARAMA/SIRALAMA (retrieval/ranking) içindir -- bkz. KAIZEN_HEDEF_VE_YOL_HARITASI.md
mimari rol sınırı: BGE-M3 asla gerçek/doğrulanmış bilgi kaynağı DEĞİLDİR, FactRegistry/
Evidence/Consensus'un yerini tutmaz. `memory/cognee_memory.py`'nin embedding yolu (Cognee'nin
kendi LiteLLM ortam değişkenleri üzerinden çağırdığı içsel yol) TAMAMEN ayrıdır ve tekrar
KULLANILAMAZ -- bu yüzden bu istemci `core/ai/local_provider.py` ile AYNI disiplinde
(urllib, `_LOCAL_HOSTS` bekçisi, `is_ready()`, ASLA raise etmeyen güvenli hata dönüşü) yeni
ve ayrı bir istemci olarak yazılmıştır. Endpoint/payload/response şekli
`tools/local_ai_smoke.py::stage_embedding` ile AYNI, zaten gerçek Ollama'ya karşı doğrulanmış
sözleşmedir (/api/embeddings, {"model","prompt"} -> {"embedding": [...]})."""
import json
import math
import urllib.error
import urllib.request
from urllib.parse import urlparse

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


class OllamaEmbeddingClient:
    """Ollama üzerinden bge-m3 embedding vektörü üretir.

    Ollama'nın soğuk başlangıcının (model belleğe ilk yüklenişi) gözlemlenen ~34sn
    sürebildiği doğrulandığı için varsayılan timeout `tools/local_ai_smoke.py`'nin
    HTTP_TIMEOUT=20 değerinden kasıtlı olarak daha yüksektir.
    """

    def __init__(self, base_url="http://localhost:11434", model_name="bge-m3", timeout=90,
                 cloud_allowed=False):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self.cloud_allowed = cloud_allowed
        self._cache_identity = None

    def cache_identity(self):
        """Resolve the installed model digest once; an updated tag gets a new cache namespace."""
        if self._cache_identity is not None:
            return self._cache_identity
        if not self.is_ready():
            return None
        try:
            with urllib.request.urlopen(self.base_url + "/api/tags", timeout=min(self.timeout, 3)) as response:
                models = json.loads(response.read().decode("utf-8")).get("models", [])
            names = {self.model_name, self.model_name + ":latest"}
            digest = next((m.get("digest") for m in models if m.get("name") in names), None)
            if digest:
                self._cache_identity = self.model_name + "@" + digest
        except Exception:
            return None
        return self._cache_identity

    def is_ready(self):
        host = (urlparse(self.base_url).hostname or "").lower()
        if host not in _LOCAL_HOSTS and not self.cloud_allowed:
            return False
        return bool(self.model_name)

    def embed(self, text):
        """Başarılıysa float listesi, başarısız/hazır-değil/boş-metin durumunda None döner --
        `core/ai/local_provider.py::LocalProvider.ask` ile aynı disiplin: ASLA raise etmez."""
        if not text or not text.strip():
            return None
        if not self.is_ready():
            return None
        payload = json.dumps({"model": self.model_name, "prompt": text}).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "/api/embeddings", data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            vector = data.get("embedding")
            if not isinstance(vector, list) or not vector:
                return None
            vector = [float(x) for x in vector]
            return vector if all(math.isfinite(x) for x in vector) and any(vector) else None
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError, TypeError):
            return None
