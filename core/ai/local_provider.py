import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

from core.ai.base_provider import BaseAIProvider

SYSTEM_PROMPT = (
    "Sen Kaizen AI'sın: Türkçe konuşan, kaynağa dayalı çalışan bir muhasebe ve mali müşavirlik yardımcısısın. "
    "Tutar, oran, hesap kodu, mevzuat veya kaynak uydurma; bilmiyorsan bilmediğini söyle."
)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class LocalProvider(BaseAIProvider):
    """Yerelde çalışan OpenAI uyumlu bir model sunucusuna bağlanır (Ollama, llama.cpp, LM Studio...).

    Yeni bilgisayar hazır olduğunda Hermes yerine bu sağlayıcı seçilir:
    config/Kaizen.json -> model.provider = "local", model.local.model_name = "<model adı>".
    """

    def __init__(self, base_url="http://localhost:11434/v1", model_name="", timeout=180,
                 cloud_allowed=False, api_key=None):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self.cloud_allowed = cloud_allowed
        self.api_key = api_key

    def is_ready(self):
        host = (urlparse(self.base_url).hostname or "").lower()
        if host not in _LOCAL_HOSTS and not self.cloud_allowed:
            return False
        return bool(self.model_name)

    def ask(self, message):
        if not self.model_name:
            return "Kaizen: Yerel model adı ayarlanmadı (config/Kaizen.json -> model.local.model_name)."
        if not self.is_ready():
            return "Kaizen: Yerel model adresi bu bilgisayarda değil ve bulut kullanımı kapalı; engellendi."
        payload = json.dumps({
            "model": self.model_name, "stream": False, "temperature": 0.2,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message}],
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.base_url + "/chat/completions", data=payload, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError, ValueError) as exc:
            return f"Kaizen: Yerel model çağrısı başarısız: {exc}"
