# INACTIVE LEGACY: removed from Kaizen-1 production on 2026-09-30.
# Preserved for historical evidence only; no runtime caller or package dependency.
"""Kaizen için Cognee (bilgi grafiği hafızası) entegrasyonu.

Doğrulanan sürüm: cognee 1.6.0 (PyPI, Python >=3.10,<3.15).
Kullanılan gerçek API (cognee/api/v1 kaynağından):
    cognee.remember(data, dataset_name=..., self_improvement=...) -> RememberResult (.status, .error)
    cognee.recall(query_text, query_type=SearchType, datasets=[...], top_k=...) -> list[RecallResponse]
    cognee.forget(dataset=...) -> dict
    cognee.config.set_llm_config / set_embedding_config / data_root_directory / system_root_directory

LLM sağlayıcısı bilinçli olarak Ollama'dır, Hermes değildir:
Hermes bir ajan CLI'ıdır (`hermes chat -q`), Cognee'nin istediği OpenAI/Ollama uyumlu
bir uç nokta sunmaz; arkasındaki model de buluttadır. Hafıza içeriği bilgisayardan çıkmaz.
Ayrıntılı gerekçe: memory/COGNEE.md
"""

import asyncio
import json
import os
import hashlib
import threading
from collections import OrderedDict
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from config.config_manager import ConfigManager
from security.redaction import redact

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

DEFAULTS = {
    "enabled": False,
    "dataset": "kaizen",
    "llm_model": "llama3.2:3b",
    "llm_endpoint": "http://localhost:11434",
    "embedding_model": "bge-m3",
    "embedding_endpoint": "http://localhost:11434/api/embed",
    "embedding_dimensions": 1024,
    "huggingface_tokenizer": "BAAI/bge-m3",
    "embedding_batch_size": 5,
    "recall_type": "CHUNKS",
    "top_k": 10,
    "self_improvement": False,
}


class CogneeMemory:
    """Kaizen metinlerini yerel Cognee grafiğine yazar ve geri çağırır.

    Her şey yereldir: LLM ve embedding Ollama'da, grafik/vektör/metaveri gömülü
    depolarda (Ladybug/Kuzu, LanceDB, SQLite) `data/cognee/` altında tutulur.
    Hazır değilse (kapalı, Ollama yok, cognee kurulu değil) hata fırlatmaz; `ok=False` döner.
    """

    def __init__(self, settings=None, storage_dir=None):
        project_dir = Path(__file__).resolve().parent.parent
        if settings is None:
            settings = (ConfigManager().get("memory", "cognee", {}) or {})
        self.settings = {**DEFAULTS, **settings}
        self.storage_dir = Path(storage_dir) if storage_dir else project_dir / "data" / "cognee"
        self._cognee = None
        self._write_lock = threading.Lock()
        self._written_keys = OrderedDict()

    # --- yapılandırma -------------------------------------------------------

    def is_ready(self):
        """Ağ çağrısı yapmadan: açık mı ve tüm uç noktalar bu bilgisayarda mı?"""
        if not self.settings["enabled"]:
            return False
        for key in ("llm_endpoint", "embedding_endpoint"):
            host = (urlparse(self.settings[key]).hostname or "").lower()
            if host not in _LOCAL_HOSTS:
                return False
        return bool(self.settings["llm_model"] and self.settings["embedding_model"])

    def _not_ready_reason(self):
        if not self.settings["enabled"]:
            return "Kaizen: Cognee hafızası kapalı (config/Kaizen.json -> memory.cognee.enabled)."
        if not self.is_ready():
            return "Kaizen: Cognee uç noktası bu bilgisayarda değil; hafıza buluta gönderilmez, engellendi."
        return None

    def build_env(self):
        """Cognee'nin `import` anında okuduğu ortam değişkenleri (docs: guides/local-setup)."""
        s = self.settings
        return {
            "TELEMETRY_DISABLED": "1",
            "ENABLE_BACKEND_ACCESS_CONTROL": "false",
            "LLM_PROVIDER": "ollama",
            "LLM_MODEL": s["llm_model"],
            # Çıplak adres: litellm Ollama'nın /api/generate yolunu kendisi ekler; /v1 404 verir.
            "LLM_ENDPOINT": s["llm_endpoint"].rstrip("/"),
            # Ollama doğrulamaz ama cognee boş anahtarda LLMAPIKeyNotSetError verir.
            "LLM_API_KEY": "ollama",
            "LLM_TEMPERATURE": "0.0",
            "LLM_MAX_COMPLETION_TOKENS": str(s.get("max_completion_tokens", 2048)),
            "COGNEE_LOGS_DIR": str((self.storage_dir / "logs").resolve()),
            "EMBEDDING_PROVIDER": "ollama",
            "EMBEDDING_MODEL": s["embedding_model"],
            "EMBEDDING_ENDPOINT": s["embedding_endpoint"],
            "EMBEDDING_DIMENSIONS": str(s["embedding_dimensions"]),
            "EMBEDDING_BATCH_SIZE": str(s["embedding_batch_size"]),
            "HUGGINGFACE_TOKENIZER": s["huggingface_tokenizer"],
        }

    def _load_cognee(self):
        if self._cognee is not None:
            return self._cognee
        os.environ.update(self.build_env())
        import cognee  # ağır içe aktarma; yalnızca gerektiğinde

        env = self.build_env()
        # `import cognee` çalışma dizinindeki .env'i override=True ile yükler;
        # Kaizen ayarlarını içe aktarmadan sonra tekrar uygulayarak onu geçersiz kılarız.
        llm_config = {
            "llm_provider": env["LLM_PROVIDER"],
            "llm_model": env["LLM_MODEL"],
            "llm_endpoint": env["LLM_ENDPOINT"],
            "llm_api_key": env["LLM_API_KEY"],
            "llm_temperature": 0.0,
            "llm_max_completion_tokens": int(env["LLM_MAX_COMPLETION_TOKENS"]),
            "structured_output_framework": "litellm_native",
        }
        # All stages stay local even if another application's environment selects a cloud model.
        for stage in ("extraction", "summarization", "query"):
            llm_config.update({f"llm_{stage}_provider": "ollama",
                f"llm_{stage}_model": env["LLM_MODEL"],
                f"llm_{stage}_endpoint": env["LLM_ENDPOINT"],
                f"llm_{stage}_api_key": "ollama"})
        cognee.config.set_llm_config(llm_config)
        cognee.config.set_embedding_config({
            "embedding_provider": env["EMBEDDING_PROVIDER"],
            "embedding_model": env["EMBEDDING_MODEL"],
            "embedding_endpoint": env["EMBEDDING_ENDPOINT"],
            "embedding_dimensions": int(env["EMBEDDING_DIMENSIONS"]),
        })
        cognee.config.set_vector_db_provider("lancedb")
        cognee.config.data_root_directory(str(self.storage_dir / "data"))
        cognee.config.system_root_directory(str(self.storage_dir / "system"))
        self._cognee = cognee
        return cognee

    # --- sağlık kontrolü ----------------------------------------------------

    def health(self, timeout=3):
        """Ollama çalışıyor mu ve gerekli modeller çekilmiş mi?"""
        reason = self._not_ready_reason()
        if reason:
            return {"ok": False, "error": reason}
        url = self.settings["llm_endpoint"].rstrip("/") + "/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                names = {m.get("name", "") for m in json.loads(response.read().decode("utf-8")).get("models", [])}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            return {"ok": False, "error": f"Kaizen: Ollama'ya ulaşılamadı ({url}): {exc}"}
        missing = [
            model for model in (self.settings["llm_model"], self.settings["embedding_model"])
            if model not in names and f"{model}:latest" not in names
        ]
        if missing:
            return {"ok": False, "error": f"Kaizen: Ollama modeli eksik: {', '.join(missing)} (ollama pull ...)."}
        return {"ok": True, "error": None}

    # --- hafıza işlemleri (async) ------------------------------------------

    async def aremember(self, text, dataset=None):
        reason = self._not_ready_reason()
        if reason:
            return {"ok": False, "error": reason}
        if not isinstance(text, str) or not text.strip():
            return {"ok": False, "error": "Kaizen: Hafızaya yazılacak metin boş."}
        cognee = self._load_cognee()
        result = await cognee.remember(
            text,
            dataset_name=dataset or self.settings["dataset"],
            self_improvement=self.settings["self_improvement"],
            raise_on_error=False,
        )
        return {
            "ok": result.status == "completed",
            "status": result.status,
            "dataset": result.dataset_name,
            "error": result.error,
        }

    async def arecall(self, query, dataset=None, top_k=None):
        reason = self._not_ready_reason()
        if reason:
            return {"ok": False, "error": reason, "results": []}
        cognee = self._load_cognee()
        responses = await cognee.recall(
            query,
            query_type=cognee.SearchType[self.settings["recall_type"]],
            datasets=[dataset or self.settings["dataset"]],
            top_k=top_k or self.settings["top_k"],
            # CHUNKS supplies memory context; session feedback generation is unnecessary.
            only_context=self.settings["recall_type"] == "CHUNKS",
        )
        results = []
        for item in responses:
            text = getattr(item, "text", None) or getattr(item, "answer", None) or getattr(item, "content", None)
            if item.source == "system":
                # "hafıza ısınıyor" / "build_failed" gibi işaretler veri değildir.
                return {"ok": False, "error": f"Kaizen: Cognee hafızası hazır değil: {text}", "results": []}
            if text:
                results.append({"text": text, "source": item.source})
        return {"ok": True, "error": None, "results": results}

    async def aforget(self, dataset=None, confirmed=False):
        """Veri kümesini (ham veri + grafik + vektör) kalıcı siler; kullanıcı onayı şarttır."""
        reason = self._not_ready_reason()
        if reason:
            return {"ok": False, "error": reason}
        if confirmed is not True:
            return {"ok": False, "error": "Kaizen: Hafıza silme kullanıcı onayı gerektirir (confirmed=True)."}
        cognee = self._load_cognee()
        summary = await cognee.forget(dataset=dataset or self.settings["dataset"])
        return {"ok": True, "error": None, "summary": summary}

    # --- Kaizen'in eşzamanlı kodundan kullanım -----------------------------

    def remember(self, text, dataset=None):
        if not self.is_ready():
            return {"ok": False, "error": self._not_ready_reason()}
        text = redact(text)
        key = hashlib.sha256(((dataset or self.settings["dataset"]) + "\n" + text).encode()).hexdigest()
        if not self._write_lock.acquire(timeout=1):
            return {"ok": False, "error": "Cognee busy"}
        try:
            if key in self._written_keys:
                return {"ok": True, "status": "duplicate", "error": None}
            async def bounded():
                return await asyncio.wait_for(self.aremember(text, dataset), self.settings.get("write_timeout", 180))
            result = asyncio.run(bounded())
            if result.get("ok"):
                self._written_keys[key] = True
                if len(self._written_keys) > 512:
                    self._written_keys.popitem(last=False)
            return result
        except Exception as exc:
            return {"ok": False, "error": type(exc).__name__}
        finally:
            self._write_lock.release()

    def recall(self, query, dataset=None, top_k=None):
        async def bounded():
            return await asyncio.wait_for(self.arecall(redact(query), dataset, top_k), self.settings.get("recall_timeout", 10))
        try:
            return asyncio.run(bounded())
        except Exception as exc:
            return {"ok": False, "error": type(exc).__name__, "results": []}

    def forget(self, dataset=None, confirmed=False):
        return asyncio.run(self.aforget(dataset, confirmed))
