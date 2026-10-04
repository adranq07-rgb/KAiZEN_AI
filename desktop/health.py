"""KAİZEN Desktop -- Ayarlar > Backend durumu. Gerçek (hafif) yoklamalar; secret ASLA gösterilmez.

Her yoklama enjekte edilebilir (`http_get`) -> ağ olmadan test edilir. API anahtarı yalnız
ortam değişkeninden okunur, yalnız Authorization başlığında kullanılır, sonuçta yalnız
'ayarlı / ayarsız' bilgisi döner."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

OK, WARN, BAD = "ok", "warn", "bad"


@dataclass
class HealthItem:
    name: str
    state: str      # ok | warn | bad
    text: str


def default_http_get(url, headers=None, timeout=6):
    """-> (status_code | None, body_bytes | b'', error_name | '')"""
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(200_000), ""
    except urllib.error.HTTPError as exc:
        return exc.code, b"", ""
    except Exception as exc:  # bağlantı reddi, zaman aşımı, DNS...
        return None, b"", type(exc).__name__


def check_nemotron(config, http_get=default_http_get, environ=None):
    environ = os.environ if environ is None else environ
    settings = config.get("model", "nemotron", {}) or {}
    env_name = settings.get("api_key_env", "NGC_API_KEY")
    base = (settings.get("base_url") or "https://integrate.api.nvidia.com/v1").rstrip("/")
    primary = config.get("model", "provider", "") == "nemotron"
    role = "birincil sağlayıcı" if primary else "birincil değil (config: model.provider)"
    key = environ.get(env_name)
    if not key:
        return HealthItem("Nemotron", WARN, f"Unavailable — {env_name} ortam değişkeni ayarlı değil · {role}")
    status, _, error = http_get(f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=8)
    if status == 200:
        return HealthItem("Nemotron", OK, f"Connected — {settings.get('model_name', '?')} · {role}")
    if status in (401, 403):
        return HealthItem("Nemotron", BAD, f"Unavailable — anahtar reddedildi (HTTP {status}) · {role}")
    return HealthItem("Nemotron", BAD, f"Unavailable — {('HTTP ' + str(status)) if status else error or 'erişilemedi'} · {role}")


def check_local_fallback(config, http_get=default_http_get):
    local = config.get("model", "local", {}) or {}
    wanted = local.get("model_name", "")
    base = (local.get("base_url") or "http://localhost:11434/v1").rstrip("/")
    root = base[:-3] if base.endswith("/v1") else base
    status, body, error = http_get(f"{root}/api/tags", timeout=4)
    if status != 200:
        return HealthItem("Yerel fallback (Ollama)", BAD, f"Unavailable — {error or 'HTTP ' + str(status)}")
    try:
        names = [m.get("name", "") for m in json.loads(body.decode("utf-8")).get("models", [])]
    except Exception:
        names = []
    if wanted and not any(n == wanted or n.startswith(wanted + ":") for n in names):
        return HealthItem("Yerel fallback (Ollama)", WARN, f"Ollama çalışıyor ama '{wanted}' modeli yüklü değil")
    return HealthItem("Yerel fallback (Ollama)", OK, f"Ready — {wanted or 'model'}")


def check_document_engine():
    try:
        from documents import ops, router  # noqa: F401
        return HealthItem("Belge motoru", OK, "Ready — " + ", ".join(s.lstrip(".") for s in ops.SUPPORTED_READ_SUFFIXES))
    except Exception as exc:
        return HealthItem("Belge motoru", BAD, f"Unavailable — {type(exc).__name__}")


def check_research(config, http_get=default_http_get):
    if not config.get("research", "research_engine_enabled", False):
        return HealthItem("Araştırma", WARN, "Kapalı (config: research.research_engine_enabled)")
    base = (config.get("research", "base_url", "http://127.0.0.1:8890") or "").rstrip("/")
    status, _, error = http_get(f"{base}/search?q=test&format=json", timeout=8)
    if status == 200:
        return HealthItem("Araştırma", OK, f"Ready — SearXNG {base}")
    return HealthItem("Araştırma", BAD, f"Unavailable — SearXNG {base} ({error or 'HTTP ' + str(status)}); Docker açık mı?")


def collect_health(config, engine_ready=True, http_get=default_http_get, environ=None):
    items = [HealthItem("Backend (KaizenEngine)", OK if engine_ready else WARN,
                        "Ready" if engine_ready else "Başlatılıyor / başlatılamadı")]
    items.append(check_nemotron(config, http_get, environ))
    items.append(check_local_fallback(config, http_get))
    items.append(check_document_engine())
    items.append(check_research(config, http_get))
    return items
