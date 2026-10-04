#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KAIZEN Yerel AI (Ollama) — GERÇEK PC SMOKE TEST.

KAIZEN ANA GELİŞTİRME EMRİ'nin istediği tek-komutluk kontrollü smoke script'i
(`tools\\research_uat.py` ile AYNI disiplin, AYNI Report/PASS-kapısı deseni --
madde 1: mimari İCAT EDİLMEDİ, yalnızca zaten var olan `core/ai/local_provider.py`,
`core/ai/provider_factory.py` gerçek kodu GERÇEK Ollama sunucusuna karşı çağrılır).

NE İÇİN: bulut/sandbox ortamından `localhost:11434` (Ollama) ERİŞİLEMEZ (ayrı ağ
ad alanı) -- bu yüzden bu script yazılıp KULLANICININ KENDİ bilgisayarında
`tools\\local_ai_smoke.bat` ile çalıştırılmak üzere teslim edilir. Ollama zaten
kurulu, `llama3.2:3b` ve `bge-m3` zaten indirilmiş kabul edilir (KURULUM YAPILMAZ).

GÜVENLİK: bu script `config/Kaizen.json`'ı ASLA (kalıcı olarak) değiştirmez --
`build_provider()` gerçek fabrika kodu, dosyadan OKUYAN gerçek `ConfigManager`
yerine küçük, duck-typed, BELLEK-İÇİ bir sahte config nesnesiyle çağrılır (`search/
provider.py::SearchProvider` Protocol'üyle AYNI dependency-injection ilkesi --
madde 61: yeni bir desen İCAT EDİLMEDİ). `data/`/`knowledge/`/`memory/`/`logs/`
dizinlerine hiç yazmaz.

ÇIKIŞ KODU: 0 = PASS, 1 = PARTIAL, 2 = FAIL, 3 = script kendisi çöktü.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.ai.local_provider import LocalProvider  # noqa: E402
from core.ai.provider_factory import build_provider  # noqa: E402
from core.ai.fallback_provider import is_failure  # noqa: E402

ARTIFACTS_DIR = ROOT / "artifacts"
REPORT_JSON = ARTIFACTS_DIR / "local_ai_smoke_report.json"
REPORT_TXT = ARTIFACTS_DIR / "local_ai_smoke_report.txt"
CONFIG_FILE = ROOT / "config" / "Kaizen.json"

OLLAMA_HOST = "http://localhost:11434"
EXPECTED_CHAT_MODEL = "llama3.2:3b"
EXPECTED_EMBED_MODEL = "bge-m3"
HTTP_TIMEOUT = 20
CHAT_TIMEOUT = 60


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class _FakeConfig:
    """`build_provider(config)`'in beklediği minimal sözleşme (`.get(section, key,
    default)`, `.cloud_allowed()`) -- gerçek `config/config_manager.py::ConfigManager`'a
    HİÇ dokunmadan, GERÇEK `build_provider`/`_make` kodunu test eder."""

    def __init__(self, provider, fallback, local_model_name, local_base_url=None):
        self._data = {
            "model": {
                "provider": provider,
                "fallback": fallback,
                "local": {
                    "base_url": local_base_url or (OLLAMA_HOST + "/v1"),
                    "model_name": local_model_name,
                    "timeout": CHAT_TIMEOUT,
                },
            },
        }

    def get(self, section, key, default=None):
        return self._data.get(section, {}).get(key, default)

    def cloud_allowed(self):
        return False


class Report:
    def __init__(self):
        self.started_at = _now_iso()
        self.stages = {}
        self.criteria = {i: {"desc": d, "passed": None, "detail": ""} for i, d in PASS_CRITERIA}
        self.notes = []
        self.gate_result = "FAIL"
        self.fatal = None

    def stage(self, key):
        return self.stages.setdefault(key, {})

    def set_criterion(self, cid, passed, detail=""):
        self.criteria[cid]["passed"] = passed
        self.criteria[cid]["detail"] = detail

    def note(self, text):
        self.notes.append(text)
        print(text, flush=True)

    def finalize_gate(self):
        values = [c["passed"] for c in self.criteria.values()]
        if all(v is True for v in values):
            self.gate_result = "PASS"
        elif any(v is True for v in values):
            self.gate_result = "PARTIAL"
        else:
            self.gate_result = "FAIL"
        return self.gate_result

    def to_dict(self):
        return {
            "started_at": self.started_at, "finished_at": _now_iso(), "stages": self.stages,
            "criteria": self.criteria, "notes": self.notes, "gate_result": self.gate_result,
            "fatal": self.fatal,
        }

    def write_files(self):
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        REPORT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        lines = ["=" * 78, "KAIZEN YEREL AI (OLLAMA) -- GERÇEK PC SMOKE TEST RAPORU", "=" * 78,
                 f"Başladı : {data['started_at']}", f"Bitti   : {data['finished_at']}",
                 f"SONUÇ   : {data['gate_result']}", ""]
        if data.get("fatal"):
            f = data["fatal"]
            lines += ["*** SCRIPT BEKLENMEDİK BİR HATAYLA DURDU ***",
                      f"  exception_type : {f.get('exception_type')}", f"  message        : {f.get('message')}", ""]
        lines.append("-- PASS/FAIL KAPISI --")
        for cid, c in data["criteria"].items():
            mark = {True: "[PASS]", False: "[FAIL]", None: "[ N/A ]"}[c["passed"]]
            lines.append(f"  {mark} {cid}. {c['desc']}")
            if c["detail"]:
                lines.append(f"          -> {c['detail']}")
        lines += ["", "-- NOTLAR --"] + [f"  {n}" for n in data["notes"]] + ["=" * 78]
        REPORT_TXT.write_text("\n".join(lines), encoding="utf-8")


PASS_CRITERIA = [
    (1, "Ollama HTTP sunucusu erişilebilir (localhost:11434)"),
    (2, f"Model listesinde '{EXPECTED_CHAT_MODEL}' var"),
    (3, f"Model listesinde '{EXPECTED_EMBED_MODEL}' var"),
    (4, "LocalProvider ile basit grounded generation başarılı (gerçek, hatasız cevap)"),
    (5, "bge-m3 embedding endpoint'i gerçek vektör döndürüyor"),
    (6, "Kaizen'in gerçek build_provider() fabrikası 'local' ile çalışıyor"),
    (7, "build_provider() zinciri, yerel model bozukken güvenle offline'a düşüyor"),
    (8, "config/Kaizen.json bu script tarafından değiştirilmedi"),
]


def _http_get_json(url, timeout=HTTP_TIMEOUT):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url, payload, timeout=HTTP_TIMEOUT):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _config_sha256():
    return hashlib.sha256(CONFIG_FILE.read_bytes()).hexdigest() if CONFIG_FILE.exists() else None


def stage_ollama_reachable(report):
    stage = report.stage("A_ollama_reachable")
    try:
        payload = _http_get_json(OLLAMA_HOST + "/api/tags")
        models = [m.get("name", "") for m in payload.get("models", [])]
        stage["models"] = models
        report.set_criterion(1, True, f"{len(models)} model listelendi")
        report.note(f"[A] Ollama erişilebilir -- {len(models)} model: {models}")
        return models
    except Exception as exc:  # noqa: BLE001
        report.set_criterion(1, False, f"Ollama'ya erişilemedi: {exc!r}")
        stage["error"] = repr(exc)
        report.note(f"[A] Ollama'ya erişilemedi -- {exc!r} (Ollama çalışıyor mu? 'ollama serve')")
        return []


def _model_present(models, expected):
    expected_base = expected.split(":")[0]
    return any(m == expected or m.split(":")[0] == expected_base for m in models)


def stage_models_present(report, models):
    if _model_present(models, EXPECTED_CHAT_MODEL):
        report.set_criterion(2, True, f"'{EXPECTED_CHAT_MODEL}' bulundu")
    else:
        report.set_criterion(2, False, f"'{EXPECTED_CHAT_MODEL}' model listesinde yok: {models}")
    if _model_present(models, EXPECTED_EMBED_MODEL):
        report.set_criterion(3, True, f"'{EXPECTED_EMBED_MODEL}' bulundu")
    else:
        report.set_criterion(3, False, f"'{EXPECTED_EMBED_MODEL}' model listesinde yok: {models}")


def stage_local_provider_generation(report):
    stage = report.stage("D_local_provider_generation")
    provider = LocalProvider(base_url=OLLAMA_HOST + "/v1", model_name=EXPECTED_CHAT_MODEL, timeout=CHAT_TIMEOUT)
    question = "Muhasebede dönemsellik kavramını tek cümleyle açıklar mısın?"
    t0 = time.monotonic()
    try:
        answer = provider.ask(question)
    except Exception as exc:  # noqa: BLE001 -- madde 26 disiplini: bu script de çökmez
        answer = f"EXCEPTION: {exc!r}"
    elapsed = round(time.monotonic() - t0, 3)
    stage.update({"question": question, "answer": answer, "elapsed_seconds": elapsed})
    ok = bool(answer) and not is_failure(answer) and not answer.startswith("EXCEPTION:")
    report.set_criterion(4, ok, f"cevap uzunluğu={len(answer or '')} ({elapsed}s)" if ok else f"başarısız: {answer!r}")
    report.note(f"[D] LocalProvider.ask() -> {'OK' if ok else 'FAIL'} ({elapsed}s): {(answer or '')[:150]!r}")


def stage_embedding(report):
    stage = report.stage("E_embedding")
    try:
        payload = _http_post_json(
            OLLAMA_HOST + "/api/embeddings",
            {"model": EXPECTED_EMBED_MODEL, "prompt": "2026 gelir vergisi tarifesi"},
            timeout=HTTP_TIMEOUT,
        )
        vector = payload.get("embedding") or []
        stage["vector_len"] = len(vector)
        ok = isinstance(vector, list) and len(vector) > 0 and all(isinstance(x, (int, float)) for x in vector[:5])
        report.set_criterion(5, ok, f"vektör boyutu={len(vector)}" if ok else f"boş/geçersiz vektör: {payload!r}"[:200])
        report.note(f"[E] bge-m3 embedding -> {'OK' if ok else 'FAIL'} (boyut={len(vector)})")
    except Exception as exc:  # noqa: BLE001
        stage["error"] = repr(exc)
        report.set_criterion(5, False, f"embedding isteği başarısız: {exc!r}")
        report.note(f"[E] bge-m3 embedding isteği başarısız -- {exc!r}")


def stage_build_provider_local(report):
    stage = report.stage("F_build_provider_local")
    fake_config = _FakeConfig(provider="local", fallback=["offline"], local_model_name=EXPECTED_CHAT_MODEL)
    try:
        chain = build_provider(fake_config)
        answer = chain.ask("SGK prim tavanı hangi kalemlerden oluşur, kısaca?")
    except Exception as exc:  # noqa: BLE001
        answer = f"EXCEPTION: {exc!r}"
    ok = bool(answer) and not is_failure(answer) and not answer.startswith("EXCEPTION:")
    stage["answer"] = answer
    report.set_criterion(6, ok, f"cevap uzunluğu={len(answer or '')}" if ok else f"başarısız: {answer!r}")
    report.note(f"[F] build_provider(provider='local') gerçek zincir -> {'OK' if ok else 'FAIL'}: {(answer or '')[:150]!r}")


def stage_build_provider_fallback(report):
    stage = report.stage("G_build_provider_fallback")
    # Kasıtlı olarak var OLMAYAN bir model adı -- LocalProvider gerçekte başarısız olur,
    # zincir (madde 26 ruhu) OfflineProvider'a güvenle düşmeli, ÇÖKMEMELİ.
    fake_config = _FakeConfig(
        provider="local", fallback=["offline"], local_model_name="kaizen-bu-model-hic-yok:latest",
    )
    try:
        chain = build_provider(fake_config)
        answer = chain.ask("Bu soru asla gerçek bir modele ulaşmamalı.")
        crashed = False
    except Exception as exc:  # noqa: BLE001
        answer = repr(exc)
        crashed = True
    stage["answer"] = answer
    ok = (not crashed) and isinstance(answer, str) and "çevrimdışı" in answer.lower()
    report.set_criterion(7, ok, f"offline fallback cevabı: {answer!r}" if ok else f"BEKLENMEYEN: crashed={crashed} answer={answer!r}")
    report.note(f"[G] bozuk yerel model -> offline fallback -> {'OK' if ok else 'FAIL'}: {answer!r}")


def _run_main_body(report):
    before_sha = _config_sha256()
    models = stage_ollama_reachable(report)
    stage_models_present(report, models)
    stage_local_provider_generation(report)
    stage_embedding(report)
    stage_build_provider_local(report)
    stage_build_provider_fallback(report)
    after_sha = _config_sha256()
    ok = before_sha == after_sha
    report.set_criterion(8, ok, "değişmedi" if ok else f"DEĞİŞTİ: {before_sha} -> {after_sha}")
    report.note(f"[H] config/Kaizen.json SHA -> {'DEĞİŞMEDİ' if ok else '*** DEĞİŞTİ ***'}")


def main():
    report = Report()
    try:
        _run_main_body(report)
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        report.fatal = {"exception_type": type(exc).__name__, "message": str(exc), "traceback": tb}
        report.note(f"*** SMOKE SCRIPT BEKLENMEYEN İSTİSNAYLA DURDU: {type(exc).__name__}: {exc} ***")
        print(tb, file=sys.stderr)

    gate = report.finalize_gate()
    if report.fatal is not None and gate == "PASS":
        gate = report.gate_result = "FAIL"
        report.note("[!] fatal hata mevcutken PASS iddia edilemez -- sonuç FAIL'e zorlandı.")

    report.note(f"=== SMOKE TEST SONUCU: {gate} ===")
    report.write_files()
    report.note(f"Rapor yazıldı: {REPORT_JSON}")
    report.note(f"Rapor yazıldı: {REPORT_TXT}")

    if report.fatal is not None:
        return 3
    return {"PASS": 0, "PARTIAL": 1, "FAIL": 2}.get(gate, 2)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        print("SMOKE SCRIPT BEKLENMEDİK ŞEKİLDE ÇÖKTÜ:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
