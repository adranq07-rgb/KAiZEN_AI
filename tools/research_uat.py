#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KAIZEN Research Engine — GERÇEK PC UAT (User Acceptance Test).

KAIZEN İŞ EMRİ #2 — ARA KONTROL / GERÇEK PC RESEARCH UAT'ın doğrudan karşılığıdır.

NE İÇİN: Bu script, Research Engine'in "kodda bağlı olması" ile "kullanıcının GERÇEK
bilgisayarında GERÇEKTEN çalışması" arasındaki farkı KANITLAMAK için var. Bulut/sandbox
ortamında 127.0.0.1:8890 (SearXNG), Docker Desktop, yerel Ollama ve kullanıcının gerçek
Hermes CLI'sine ERİŞİLEMEZ (madde 2) -- bu yüzden bu script yazılıp KULLANICININ KENDİ
makinesinde `tools\\research_uat.bat` ile ya da doğrudan `python tools/research_uat.py`
ile çalıştırılmak üzere teslim edilir.

MİMARİ İCAT EDİLMEDİ (madde 1): bu script hiçbir yeni iş mantığı YAZMAZ -- yalnızca
zaten var olan `research/`, `search/`, `core/kaizen_brain.py` modüllerini GERÇEK
girdilerle ÇAĞIRIR ve gözlemlediğini dürüstçe raporlar. Tek istisna: adversarial
testler için gerçek `Evidence`/`Claim` nesneleri üzerinde KONTROLLÜ mutasyon
(`dataclasses.replace`) kullanılır (bkz. `_temporal_adversarial_check` ve
`_conflict_adversarial_check`) -- bu da yeni doğrulama mantığı YAZMAZ, yalnızca
GERÇEK verifier/consensus kodunu GERÇEK ama kontrollü biçimde değiştirilmiş girdilerle
tekrar çağırır.

GÜVENLİK (madde 13, 23, 26): bu script asla `research/fetcher.py::SafeFetcher`'ın
robots/SSRF/redirect/boyut/timeout kurallarını gevşetmez, asla `config/Kaizen.json`
dosyasını (kalıcı olarak) değiştirmez, asla `settings.yml`'yi kendiliğinden düzenlemez,
asla `data/`/`knowledge/`/`memory/`/`logs/` dizinlerine yazmaz (yalnızca `artifacts/`
ve işletim-sistemi geçici dizinleri kullanılır) ve Research Engine kendi içinde zaten
hiçbir zaman raise etmediği için (madde 26) bu script de her aşamayı ayrı ayrı
try/except ile sarar -- bir aşamanın çökmesi diğerlerinin çalışmasını engellemez.

ÇIKIŞ KODU: 0 = PASS, 1 = PARTIAL, 2 = FAIL, 3 = script kendisi çöktü (beklenmeyen).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ARTIFACTS_DIR = ROOT / "artifacts"
REPORT_JSON = ARTIFACTS_DIR / "research_uat_report.json"
REPORT_TXT = ARTIFACTS_DIR / "research_uat_report.txt"

# madde 23: bu script SHA disiplinini bozmamak için data/ değil, artifacts/ kullanır.
GUARDED_DIRS = ("data", "knowledge", "memory", "logs")

SEARXNG_BASE_URL = "http://127.0.0.1:8890"
DOCKER_CONTAINER_NAME = "kaizen-searxng"

# madde 6/8: yavaş, kontrollü sorgular -- provider'ın kendi burst korumasına güvenilir,
# ayrıca aralara ek bekleme de eklenir.
ENGINE_HEALTH_QUERIES = [
    "muhasebe dönemsellik kavramı",
    "2026 gelir vergisi tarifesi",
    "site:gov.tr prime esas kazanç 2026",
]

# madde 11: aynen verilen 5 soru, birebir.
RESEARCH_QUESTIONS = [
    ("A", "2026 gelir vergisi tarifesi nedir?"),
    ("B", "2026 SGK prime esas kazanç alt ve üst sınırı nedir?"),
    ("C", "Muhasebede dönemsellik kavramı nedir?"),
    ("D", "2026 yeniden değerleme oranı nedir?"),
    ("E", "4/a, 4/b ve 4/c arasındaki temel fark nedir?"),
]

BRAIN_TIMEOUT_SECONDS = 120.0

_executor = ThreadPoolExecutor(max_workers=1)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _run_with_timeout(fn, timeout, *args, **kwargs):
    """Hermes/yerel model çağrıları donarsa (madde 2: bulut sınırının simetriği --
    gerçek PC'de bile yerel model/Hermes CLI yanıt vermeyebilir) tüm UAT'ı ASLA
    sonsuza kadar bloklamaz. Timeout'ta (None, 'TIMEOUT') döner, script çökmez."""
    future = _executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout), None
    except FutureTimeoutError:
        return None, "TIMEOUT"
    except Exception as exc:  # noqa: BLE001 -- madde 26 disiplini: hiçbir aşama script'i çökertmez
        return None, f"EXCEPTION: {exc!r}"


class Report:
    """Tüm UAT çıktısının tek, sıralı, JSON-serileştirilebilir birikimi."""

    def __init__(self):
        self.started_at = _now_iso()
        self.stages = {}
        self.criteria = {i: {"desc": desc, "passed": None, "detail": ""} for i, desc in PASS_CRITERIA}
        self.notes = []
        self.gate_result = "FAIL"
        self.current_stage_label = "init"
        self.fatal = None  # None ya da {"fatal_stage","exception_type","message","traceback"}

    def stage(self, key):
        return self.stages.setdefault(key, {})

    def mark(self, label):
        """UAT bulgusu (2026-09-24, ikinci gerçek PC koşusu): script beklenmedik biçimde
        çökerse `main()`'in dışındaki bir yerin BİLE hangi aşamada olduğumuzu bilmesi
        gerekiyor -- her aşamaya girmeden önce çağrılır, en son çağrılan değer
        `self.fatal['fatal_stage']`'e yazılır."""
        self.current_stage_label = label

    def set_criterion(self, cid, passed, detail=""):
        if cid not in self.criteria:
            raise KeyError(f"bilinmeyen kriter id: {cid}")
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
            "started_at": self.started_at,
            "finished_at": _now_iso(),
            "stages": self.stages,
            "criteria": self.criteria,
            "notes": self.notes,
            "gate_result": self.gate_result,
            "fatal": self.fatal,
        }

    def write_files(self):
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        REPORT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        REPORT_TXT.write_text(_render_txt(data), encoding="utf-8")


# madde 24: PASS kapısının 16 kriteri, birebir.
PASS_CRITERIA = [
    (1, "Docker erişilebilir"),
    (2, "kaizen-searxng running"),
    (3, "HTTP endpoint erişilebilir"),
    (4, "JSON API gerçek sonuç döndürüyor"),
    (5, "SearXNGProvider gerçek instance'tan sonuç alıyor"),
    (6, "Research Engine gerçek SearchProvider'ı kullanıyor"),
    (7, "En az bir gerçek URL başarıyla fetch ediliyor"),
    (8, "Evidence gerçekten extracted content'ten oluşuyor"),
    (9, "Snippet-only veri verified claim olmuyor"),
    (10, "Yanlış dönem SUPPORTED olmuyor"),
    (11, "Alakasız ama güvenilir kaynak SUPPORTED olmuyor"),
    (12, "Sayısal claim consensus/official-source güvenlik kuralını geçiyor"),
    (13, "KaizenBrain ON modunda Research Engine'e gerçekten giriyor"),
    (14, "Research SUPPORTED olduğunda Hermes fallback kullanılmıyor"),
    (15, "Research yetersiz olduğunda mevcut fallback güvenli kalıyor"),
    (16, "data/knowledge/memory/logs değişmiyor"),
]


def _render_txt(data):
    lines = []
    lines.append("=" * 78)
    lines.append("KAIZEN RESEARCH ENGINE — GERÇEK PC UAT RAPORU")
    lines.append("=" * 78)
    lines.append(f"Başladı : {data['started_at']}")
    lines.append(f"Bitti   : {data['finished_at']}")
    lines.append(f"SONUÇ   : {data['gate_result']}")
    if data.get("fatal"):
        f = data["fatal"]
        lines.append("")
        lines.append("*** UAT SCRIPT'İ BEKLENMEDİK BİR HATAYLA DURDU (rapor yine de TAM yazıldı) ***")
        lines.append(f"  fatal_stage    : {f.get('fatal_stage')}")
        lines.append(f"  exception_type : {f.get('exception_type')}")
        lines.append(f"  message        : {f.get('message')}")
        lines.append("  (tam traceback için research_uat_report.json veya konsol çıktısına bakın)")
    lines.append("")
    lines.append("-- PASS/FAIL KAPISI (madde 24, 16 kriter) --")
    for cid, c in data["criteria"].items():
        mark = {True: "[PASS]", False: "[FAIL]", None: "[ N/A ]"}[c["passed"]]
        lines.append(f"  {mark} {cid}. {c['desc']}")
        if c["detail"]:
            lines.append(f"          -> {c['detail']}")
    lines.append("")
    lines.append("-- AŞAMA DETAYLARI --")
    for key, stage in data["stages"].items():
        lines.append(f"[{key}]")
        lines.append(json.dumps(stage, ensure_ascii=False, indent=2, default=str))
        lines.append("")
    lines.append("-- NOTLAR (kronolojik) --")
    for n in data["notes"]:
        lines.append(f"  {n}")
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------------
# SHA256 bütünlük muhafızı (madde 23)
# ---------------------------------------------------------------------------------
# UAT bulgusu (2026-09-24, kullanıcının GERÇEK ikinci Windows koşusu): eski `_sha_snapshot()`
# `path.read_bytes()`'i çıplak çağırıyordu -- Windows'ta kilitli/erişilemeyen tek bir dosya
# (ör. başka bir süreç tarafından açık tutulan bir sqlite dosyası) TÜM UAT script'ini
# `PermissionError` ile ÇÖKERTİYORDU (madde 26 ihlali: bir aşama TÜM script'i çökertmemeli --
# bu disiplin SHA muhafızının KENDİSİNE de uygulanmamıştı). Düzeltme: her giriş AÇIKÇA
# sınıflandırılır (HASHED / SKIPPED_PERMISSION / SKIPPED_SPECIAL / ERROR), hiçbiri sessizce
# yutulmaz -- `skipped` listesi tam yol + tür + ayrıntıyla rapora yazılır. Bir dosya
# hash'lenemediğinde script'in KENDİSİ asla "bütünlük doğrulandı" DEMEZ (bkz. main()'deki
# INTEGRITY_PARTIAL kararı).

_ENTRY_HASHED = "HASHED"
_ENTRY_SKIPPED_PERMISSION = "SKIPPED_PERMISSION"
_ENTRY_SKIPPED_SPECIAL = "SKIPPED_SPECIAL"
_ENTRY_ERROR = "ERROR"


def _classify_entry_type(path):
    """Bir dosya sistemi girdisinin TÜRÜNÜ, ondan hash ALMADAN ÖNCE belirler -- normal
    dosya / dizin / symlink-junction-reparse point / stat sırasında hata. `path.is_symlink()`
    Windows junction/reparse point'leri de kapsar (pathlib bunları symlink olarak raporlar)."""
    try:
        if path.is_symlink():
            return "symlink_or_reparse_point"
        if path.is_dir():
            return "directory"
        if path.is_file():
            return "regular_file"
        return "special_or_unknown"
    except OSError as exc:
        return f"stat_error:{exc!r}"


def _sha_snapshot():
    """Korunan dizinleri (`GUARDED_DIRS`) tarar. Döner: `(hashes, skipped)` --
    `hashes`: {göreli_yol: sha256} yalnız GERÇEKTEN hash'lenebilen normal dosyalar.
    `skipped`: [{"path", "classification", "type", "detail"}] -- hash'LENEMEYEN HER giriş
    (izin hatası, symlink/junction, başka bir stat/okuma hatası) burada, GİZLENMEDEN
    listelenir. Bu fonksiyon KENDİSİ asla raise etmez (madde 26 -- artık SHA muhafızına da
    uygulanıyor)."""
    hashes = {}
    skipped = []
    for name in GUARDED_DIRS:
        d = ROOT / name
        if not d.is_dir():
            continue
        try:
            entries = sorted(d.rglob("*"))
        except OSError as exc:
            skipped.append({"path": str(d), "classification": _ENTRY_ERROR,
                             "type": "directory_walk_failed", "detail": repr(exc)})
            continue
        for path in entries:
            rel = path.relative_to(ROOT).as_posix()
            entry_type = _classify_entry_type(path)
            if entry_type == "directory":
                continue  # dizinlerin kendisi hash'lenmez, yalnız içindeki dosyalar
            if entry_type == "symlink_or_reparse_point":
                skipped.append({
                    "path": rel, "classification": _ENTRY_SKIPPED_SPECIAL, "type": entry_type,
                    "detail": "symlink/junction/reparse point -- hash edilmedi (içeriği başka bir "
                              "gerçek dosyaya ait olabilir, iki kez sayılmasın diye atlandı)",
                })
                continue
            if entry_type.startswith("stat_error:"):
                skipped.append({"path": rel, "classification": _ENTRY_ERROR, "type": "stat_error",
                                 "detail": entry_type})
                continue
            if entry_type != "regular_file":
                skipped.append({"path": rel, "classification": _ENTRY_SKIPPED_SPECIAL,
                                 "type": entry_type, "detail": "normal dosya/dizin/symlink değil"})
                continue
            try:
                h = hashlib.sha256()
                h.update(path.read_bytes())
                hashes[rel] = h.hexdigest()
            except PermissionError as exc:
                skipped.append({
                    "path": rel, "classification": _ENTRY_SKIPPED_PERMISSION, "type": "regular_file",
                    "detail": f"{exc!r} -- muhtemelen başka bir süreç tarafından kilitli/açık "
                              "(ör. bir veritabanı bağlantısı) ya da izin reddedildi",
                })
            except OSError as exc:
                skipped.append({"path": rel, "classification": _ENTRY_ERROR, "type": "regular_file",
                                 "detail": repr(exc)})
    return hashes, skipped


# ---------------------------------------------------------------------------------
# AŞAMA A: Docker (madde 4)
# ---------------------------------------------------------------------------------

SEARXNG_PORT = str(urllib.parse.urlparse(SEARXNG_BASE_URL).port)

# madde 6 (yeni talimat): Docker teşhisi daha GRANÜLER hale getirildi -- eskiden tek bir
# "FAIL_DOCKER_UNAVAILABLE" sonucu "CLI PATH'te yok" ile "CLI var ama daemon çalışmıyor"u
# ayırt etmiyordu. `stage["result"]` (FAIL_DOCKER_UNAVAILABLE/FAIL_DOCKER_CONTAINER/
# FAIL_SEARXNG_STOPPED/OK) MEVCUT testlerle uyumluluk için AYNEN korunur -- yeni
# sınıflandırma `stage["docker_diagnosis"]` / `stage["container_diagnosis"]` gibi EK
# alanlar olarak eklenir, hiçbiri var olanı DEĞİŞTİRMEZ/gevşetmez.
_DOCKER_CLI_NOT_FOUND = "DOCKER_CLI_NOT_FOUND"
_DOCKER_DESKTOP_NOT_RUNNING = "DOCKER_DESKTOP_NOT_RUNNING"
_DOCKER_DAEMON_UNREACHABLE = "DOCKER_DAEMON_UNREACHABLE"
_DOCKER_PERMISSION_ERROR = "DOCKER_PERMISSION_ERROR"
_DOCKER_UNKNOWN_ERROR = "UNKNOWN_DOCKER_ERROR"

_CONTAINER_NOT_FOUND = "CONTAINER_NOT_FOUND"
_CONTAINER_STOPPED = "CONTAINER_STOPPED"
_CONTAINER_RUNNING = "CONTAINER_RUNNING"


def _classify_docker_daemon_error(exc, stderr_text):
    """`docker version` (daemon erişilebilirlik) çağrısı başarısız olduğunda KABACA
    'Docker çalışmıyor' demek yerine sebebi sınıflandırır. Hem gerçek subprocess
    istisnalarını (`exc`, örn. `FileNotFoundError`) hem docker CLI'nin platform-bağımlı
    stderr metnini (Windows named pipe hatası, Linux unix socket hatası, izin hatası vb.)
    dikkate alır. `exc=None` olabilir (yalnızca returncode != 0, istisna yok)."""
    if isinstance(exc, FileNotFoundError):
        return _DOCKER_CLI_NOT_FOUND
    lowered = (stderr_text or "").lower()
    if "permission denied" in lowered or "access is denied" in lowered or "accessdenied" in lowered:
        return _DOCKER_PERMISSION_ERROR
    desktop_not_running_hints = (
        "cannot connect to the docker daemon",
        "docker desktop is starting",
        "docker desktop is not running",
        "is the docker daemon running",
        "pipe/docker_engine",
        "dockerdesktoplinuxengine",
        "the system cannot find the file specified",
        "no such file or directory",
        "connection refused",
    )
    if any(h in lowered for h in desktop_not_running_hints):
        return _DOCKER_DESKTOP_NOT_RUNNING
    if exc is not None and "timeout" in type(exc).__name__.lower():
        return _DOCKER_DAEMON_UNREACHABLE
    if lowered.strip():
        return _DOCKER_DAEMON_UNREACHABLE
    return _DOCKER_UNKNOWN_ERROR


def stage_docker(report):
    stage = report.stage("A_docker")

    # 1) CLI VARLIĞI -- `shutil.which` bir subprocess ÇALIŞTIRMADAN PATH'i kontrol eder;
    # bu, "docker komutu hiç PATH'te yok" durumunu (DOCKER_CLI_NOT_FOUND) daemon'a hiç
    # dokunmadan, ayrı bir kontrol olarak tespit eder (madde 6: "CLI var ama daemon
    # calismiyor" ile "PATH'te hic yok" ayrımı).
    docker_path = shutil.which("docker")
    if not docker_path:
        stage["result"] = "FAIL_DOCKER_UNAVAILABLE"
        stage["docker_diagnosis"] = _DOCKER_CLI_NOT_FOUND
        stage["detail"] = "docker komutu PATH'te bulunamadı."
        report.set_criterion(1, False, f"{_DOCKER_CLI_NOT_FOUND}: docker komutu PATH'te bulunamadı")
        report.set_criterion(2, False, "Docker erişilemediği için container kontrol edilemedi")
        report.note(f"[A] {_DOCKER_CLI_NOT_FOUND}: Docker komutu bulunamadı -- Docker Desktop kurulu/PATH'te değil.")
        return stage
    stage["docker_cli_path"] = docker_path

    # 2) DAEMON ERİŞİLEBİLİRLİĞİ -- `docker version` GERÇEKTEN daemon'a bağlanmayı dener
    # (CLI'nin kendisi PATH'te olsa da daemon kapalıysa bu adım başarısız olur).
    version_exc = None
    version_proc = None
    try:
        version_proc = subprocess.run(
            ["docker", "version", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        version_exc = exc

    if version_exc is not None:
        diagnosis = _classify_docker_daemon_error(version_exc, "")
        stage["result"] = "FAIL_DOCKER_UNAVAILABLE"
        stage["docker_diagnosis"] = diagnosis
        stage["detail"] = f"docker version çalıştırılamadı: {version_exc!r}"
        report.set_criterion(1, False, f"{diagnosis}: docker version çalıştırılamadı: {version_exc!r}")
        report.set_criterion(2, False, "Docker erişilemediği için container kontrol edilemedi")
        report.note(f"[A] {diagnosis}: docker version çalıştırılamadı: {version_exc!r}")
        return stage

    if version_proc.returncode != 0:
        stderr_text = (version_proc.stderr or "").strip()
        diagnosis = _classify_docker_daemon_error(None, stderr_text)
        stage["result"] = "FAIL_DOCKER_UNAVAILABLE"
        stage["docker_diagnosis"] = diagnosis
        stage["detail"] = stderr_text[:2000]
        report.set_criterion(1, False, f"{diagnosis}: docker version komutu başarısız döndü -- {stderr_text[:300]}")
        report.set_criterion(2, False, "Docker erişilemediği için container kontrol edilemedi")
        report.note(f"[A] {diagnosis}: Docker daemon'a erişilemiyor (docker version başarısız) "
                     f"-- stderr: {stderr_text[:300]!r}")
        return stage

    stage["docker_version_ok"] = True
    report.set_criterion(1, True, "docker version başarılı (CLI + daemon erişilebilir)")
    report.note("[A] Docker CLI + daemon erişilebilir.")

    # 3) CONTAINER DURUMU -- `docker inspect` ile NOT_FOUND / STOPPED / RUNNING ayrımı,
    # RUNNING ise 8890 port mapping'i AÇIKÇA doğrulanır (madde 6). Container'ı asla
    # silmez/yeniden oluşturmaz -- yalnız GÖZLEMLER (mevcut kısıt korunuyor).
    try:
        inspect_proc = subprocess.run(
            ["docker", "inspect", DOCKER_CONTAINER_NAME],
            capture_output=True, text=True, timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        stage["result"] = "FAIL_DOCKER_CONTAINER"
        stage["container_diagnosis"] = _CONTAINER_NOT_FOUND
        stage["detail"] = f"docker inspect çalıştırılamadı: {exc!r}"
        report.set_criterion(2, False, f"docker inspect çalıştırılamadı: {exc!r}")
        report.note(f"[A] docker inspect çalıştırılamadı: {exc!r}")
        return stage

    if inspect_proc.returncode != 0:
        stage["result"] = "FAIL_DOCKER_CONTAINER"
        stage["container_diagnosis"] = _CONTAINER_NOT_FOUND
        stage["detail"] = f"'{DOCKER_CONTAINER_NAME}' container'ı bulunamadı."
        report.set_criterion(2, False, f"{_CONTAINER_NOT_FOUND}: '{DOCKER_CONTAINER_NAME}' container'ı yok")
        report.note(f"[A] {_CONTAINER_NOT_FOUND}: '{DOCKER_CONTAINER_NAME}' container'ı yok.")
        return stage

    try:
        info = json.loads(inspect_proc.stdout)[0]
    except Exception as exc:  # noqa: BLE001
        stage["result"] = "FAIL_DOCKER_CONTAINER"
        stage["container_diagnosis"] = _CONTAINER_NOT_FOUND
        stage["detail"] = f"docker inspect çıktısı ayrıştırılamadı: {exc!r}"
        report.set_criterion(2, False, f"docker inspect çıktısı ayrıştırılamadı: {exc!r}")
        report.note(f"[A] docker inspect JSON ayrıştırılamadı: {exc!r}")
        return stage

    state = info.get("State", {})
    status = state.get("Status")
    health = (state.get("Health") or {}).get("Status")
    ports = info.get("NetworkSettings", {}).get("Ports", {})

    stage["exists"] = True
    stage["running"] = bool(state.get("Running"))
    stage["status"] = status
    stage["health"] = health
    stage["port_mapping"] = ports

    if not state.get("Running"):
        stage["result"] = "FAIL_SEARXNG_STOPPED"
        stage["container_diagnosis"] = _CONTAINER_STOPPED
        report.set_criterion(2, False, f"{_CONTAINER_STOPPED}: container durumu = {status!r} (running değil)")
        report.note(f"[A] {_CONTAINER_STOPPED}: container durumu = {status!r}")
        return stage

    # RUNNING -- port 8890 mapping'de gerçekten var mı? (madde 6: "açıkça doğrulanmalı")
    host_ports_seen = set()
    for _container_port, bindings in (ports or {}).items():
        for b in (bindings or []):
            hp = b.get("HostPort")
            if hp:
                host_ports_seen.add(str(hp))
    port_ok = SEARXNG_PORT in host_ports_seen
    stage["container_diagnosis"] = _CONTAINER_RUNNING
    stage["host_ports_seen"] = sorted(host_ports_seen)
    stage["port_8890_ok"] = port_ok

    if not port_ok:
        stage["result"] = "FAIL_SEARXNG_PORT_MISMATCH"
        report.set_criterion(
            2, False,
            f"{_CONTAINER_RUNNING} ama port {SEARXNG_PORT} port mapping'inde YOK "
            f"(görülen host portları: {sorted(host_ports_seen)}) -- status={status} health={health}",
        )
        report.note(f"[A] *** container RUNNING ama port {SEARXNG_PORT} mapping'de bulunamadı! "
                     f"host portları: {sorted(host_ports_seen)} ***")
        return stage

    stage["result"] = "OK"
    report.set_criterion(2, True, f"{_CONTAINER_RUNNING}, port {SEARXNG_PORT} doğrulandı, "
                                    f"status={status} health={health} ports={ports}")
    report.note(f"[A] kaizen-searxng RUNNING, port {SEARXNG_PORT} doğrulandı (status={status}, health={health}).")
    return stage


# ---------------------------------------------------------------------------------
# AŞAMA B: SearXNG HTTP + /config (madde 5)
# ---------------------------------------------------------------------------------

def _http_get(url, timeout=15.0, accept="text/html"):
    req = urllib.request.Request(url, headers={"User-Agent": "KaizenUAT/1.0", "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


def stage_http(report):
    stage = report.stage("B_http")
    try:
        status, ctype, _body = _http_get(SEARXNG_BASE_URL, accept="text/html")
        stage["root_status"] = status
        stage["root_content_type"] = ctype
        report.note(f"[B] SearXNG ana endpoint erişilebilir (HTTP {status}).")
    except Exception as exc:  # noqa: BLE001
        stage["result"] = "FAIL_HTTP_UNREACHABLE"
        stage["detail"] = repr(exc)
        report.note(f"[B] SearXNG HTTP erişilemedi: {exc!r}")
        return stage

    try:
        cstatus, cctype, cbody = _http_get(f"{SEARXNG_BASE_URL}/config", accept="application/json")
        payload = json.loads(cbody.decode("utf-8", errors="replace"))
        engines = payload.get("engines") or []
        enabled = [e for e in engines if not e.get("disabled")]
        categories = sorted({e.get("categories", [None])[0] for e in enabled if e.get("categories")})
        stage["config_status"] = cstatus
        stage["engine_count_enabled"] = len(enabled)
        stage["engine_names"] = sorted({e.get("name") for e in enabled if e.get("name")})
        stage["categories"] = categories
        report.set_criterion(3, True, f"/config HTTP {cstatus}, enabled_engines={len(enabled)}")
        report.note(f"[B] /config OK -- {len(enabled)} aktif motor: {stage['engine_names']}")
    except Exception as exc:  # noqa: BLE001
        # /config erişilemese bile ana endpoint çalıştığı için HTTP kriteri yine de PASS
        # sayılabilir (madde 5 yalnız /config'i "ayrıca" ister) -- ama gözlemi gizleme.
        report.set_criterion(3, True, "ana endpoint OK, /config okunamadı (detay: stage.config_error)")
        stage["config_error"] = repr(exc)
        report.note(f"[B] /config okunamadı (ana endpoint yine de erişilebilir): {exc!r}")

    stage.setdefault("result", "OK")
    return stage


# ---------------------------------------------------------------------------------
# AŞAMA C: JSON API (madde 6-7)
# ---------------------------------------------------------------------------------

def _searxng_json_search(query, timeout=15.0):
    params = {"q": query, "format": "json"}
    url = f"{SEARXNG_BASE_URL}/search?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "KaizenUAT/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = resp.status
        ctype = resp.headers.get("Content-Type", "")
        body = resp.read()
    return status, ctype, body


def stage_json_api(report):
    stage = report.stage("C_json_api")
    query = "muhasebe dönemsellik kavramı"
    try:
        status, ctype, body = _searxng_json_search(query)
    except urllib.error.HTTPError as exc:
        stage["http_status"] = exc.code
        if exc.code == 403:
            stage["result"] = "FAIL_JSON_FORMAT_DISABLED"
            stage["diagnosis"] = (
                "SearXNG JSON API 403 döndürdü. Bu genellikle settings.yml içinde "
                "'search.formats' listesinin 'json'u İÇERMEMESİNDEN kaynaklanır. "
                "UAT script'i settings.yml'yi KENDİLİĞİNDEN DEĞİŞTİRMEZ (madde 7). "
                "Beklenen yapı (settings.yml):\n"
                "  search:\n    formats:\n      - html\n      - json\n"
                "Bu satırı ekleyip SearXNG container'ını yeniden başlattıktan sonra "
                "UAT'ı tekrar çalıştırın."
            )
            report.note("[C] FAIL_JSON_FORMAT_DISABLED (HTTP 403) -- teşhis raporda, settings.yml'ye dokunulmadı.")
        else:
            stage["result"] = f"FAIL_HTTP_{exc.code}"
            report.note(f"[C] JSON API HTTP {exc.code} hatası.")
        return stage
    except Exception as exc:  # noqa: BLE001
        stage["result"] = "FAIL_JSON_API_UNREACHABLE"
        stage["detail"] = repr(exc)
        report.note(f"[C] JSON API erişilemedi: {exc!r}")
        return stage

    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        stage["result"] = "FAIL_JSON_PARSE"
        stage["detail"] = repr(exc)
        report.note(f"[C] JSON gövdesi ayrıştırılamadı: {exc!r}")
        return stage

    results = payload.get("results") or []
    stage["http_status"] = status
    stage["content_type"] = ctype
    stage["results_count"] = len(results)
    stage["first_5"] = [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "engine": r.get("engine"),
            "score": r.get("score"),
            "publishedDate": r.get("publishedDate"),
        }
        for r in results[:5]
    ]

    if not results:
        stage["result"] = "SEARXNG_EMPTY"
        report.note("[C] HTTP 200 ama results=0 -- SEARXNG_EMPTY (PASS SAYILMADI).")
        return stage

    stage["result"] = "OK"
    report.set_criterion(4, True, f"{len(results)} gerçek sonuç, HTTP {status}")
    report.note(f"[C] JSON API {len(results)} gerçek sonuç döndürdü.")
    return stage


# ---------------------------------------------------------------------------------
# AŞAMA D: Engine health (madde 8-9)
# ---------------------------------------------------------------------------------

_CAPTCHA_HINTS = ("captcha",)
_RATE_LIMIT_HINTS = ("429", "rate limit", "too many request")
_TIMEOUT_HINTS = ("timeout", "timed out")


def _classify_engine_reason(reason):
    lowered = (reason or "").lower()
    if any(h in lowered for h in _CAPTCHA_HINTS):
        return "CAPTCHA"
    if any(h in lowered for h in _RATE_LIMIT_HINTS):
        return "RATE_LIMITED"
    if any(h in lowered for h in _TIMEOUT_HINTS):
        return "TIMEOUT"
    return "UNAVAILABLE"


def stage_engine_health(report):
    stage = report.stage("D_engine_health")
    queries_report = []
    for i, query in enumerate(ENGINE_HEALTH_QUERIES):
        entry = {"query": query}
        t0 = time.monotonic()
        try:
            status, _ctype, body = _searxng_json_search(query)
            payload = json.loads(body.decode("utf-8", errors="replace"))
            results = payload.get("results") or []
            unresponsive = payload.get("unresponsive_engines") or []
            responding = sorted({r.get("engine") for r in results if r.get("engine")})
            entry.update({
                "http_status": status,
                "result_count": len(results),
                "responding_engines": responding,
                "unresponsive_engines": unresponsive,
                "unresponsive_classified": [
                    {"engine": u[0] if isinstance(u, (list, tuple)) and len(u) > 0 else str(u),
                     "reason": u[1] if isinstance(u, (list, tuple)) and len(u) > 1 else "",
                     "classified_as": _classify_engine_reason(
                         u[1] if isinstance(u, (list, tuple)) and len(u) > 1 else ""
                     )}
                    for u in unresponsive
                ],
                "latency_seconds": round(time.monotonic() - t0, 3),
            })
            if results and unresponsive:
                entry["overall"] = "DEGRADED"
            elif results:
                entry["overall"] = "OK"
            else:
                entry["overall"] = "EMPTY" if not unresponsive else "DEGRADED"
        except urllib.error.HTTPError as exc:
            entry["overall"] = "RATE_LIMITED" if exc.code == 429 else f"HTTP_{exc.code}"
            entry["latency_seconds"] = round(time.monotonic() - t0, 3)
        except Exception as exc:  # noqa: BLE001
            entry["overall"] = "UNAVAILABLE"
            entry["error"] = repr(exc)
            entry["latency_seconds"] = round(time.monotonic() - t0, 3)
        queries_report.append(entry)
        report.note(f"[D] '{query}' -> {entry.get('overall')} "
                    f"({entry.get('result_count', '?')} sonuç, {entry.get('latency_seconds')}s)")
        if i < len(ENGINE_HEALTH_QUERIES) - 1:
            time.sleep(2.0)  # madde 8: sorgular arasında kontrollü bekleme

    stage["queries"] = queries_report
    any_ok_or_degraded = any(e.get("overall") in ("OK", "DEGRADED") for e in queries_report)
    stage["result"] = "OK" if any_ok_or_degraded else "ALL_UNAVAILABLE"
    # madde 9: bir motor düşse bile en az bir sorguda gerçek sonuç geldiyse tüm sistemi
    # DOWN ilan etmiyoruz.
    if any_ok_or_degraded:
        report.note("[D] En az bir sorgu OK/DEGRADED -- tek motor arızası sistemi DOWN yapmıyor.")
    else:
        report.note("[D] Hiçbir sorgu sonuç vermedi -- motor sağlığı ciddi şekilde bozuk.")
    return stage


# ---------------------------------------------------------------------------------
# AŞAMA E: SearXNGProvider gerçek instance (madde 10)
# ---------------------------------------------------------------------------------

def stage_searxng_provider(report):
    stage = report.stage("E_searxng_provider")
    from search.provider import SearchOptions
    from search.searxng_provider import SearXNGProvider

    provider = SearXNGProvider()  # gerçek, varsayılan 127.0.0.1:8890 -- MOCK YOK
    queries_report = []
    any_ok = False
    for i, query in enumerate(ENGINE_HEALTH_QUERIES):
        entry = {"query": query}
        t0 = time.monotonic()
        try:
            outcome = provider.search(query, SearchOptions(limit=5))
            entry.update({
                "status": outcome.status,
                "result_count": len(outcome.results),
                "engines_failed": list(outcome.engines_failed),
                "single_engine_dependency": outcome.single_engine_dependency,
                "fallback_recommended": outcome.fallback_recommended,
                "fallback_reason": outcome.fallback_reason,
                "latency_seconds": round(time.monotonic() - t0, 3),
            })
            if outcome.results:
                any_ok = True
        except Exception as exc:  # noqa: BLE001
            entry["exception"] = repr(exc)
            entry["status"] = getattr(exc, "status", "ERROR")
            entry["latency_seconds"] = round(time.monotonic() - t0, 3)
        debug = provider.last_search_debug
        if debug is not None:
            entry["debug"] = {
                "attempt_count": debug.attempt_count,
                "elapsed": round(debug.elapsed, 3),
                "active_engines": list(debug.active_engines),
            }
        health = provider.health
        entry["provider_health_after"] = {
            "state": health.state,
            "consecutive_failures": health.consecutive_failures,
            "last_status": health.last_status,
            "cooldown_until": health.cooldown_until,
        }
        queries_report.append(entry)
        report.note(f"[E] SearXNGProvider('{query}') -> status={entry.get('status')} "
                    f"n={entry.get('result_count', '?')} health={health.state}")
        if i < len(ENGINE_HEALTH_QUERIES) - 1:
            time.sleep(1.0)

    stage["queries"] = queries_report
    stage["result"] = "OK" if any_ok else "NO_RESULTS"
    if any_ok:
        report.set_criterion(5, True, "SearXNGProvider gerçek instance en az 1 sorguda gerçek sonuç döndürdü")
    else:
        report.set_criterion(5, False, "SearXNGProvider hiçbir sorguda sonuç döndürmedi")
    return stage, provider


# ---------------------------------------------------------------------------------
# AŞAMA F: Research Engine gerçek test (madde 11-12)
# ---------------------------------------------------------------------------------

class _CountingProviderWrapper:
    """`SearchProvider` sözleşmesini DEĞİŞTİRMEDEN (madde 10: 'public contract'ı bozma)
    yalnızca GÖZLEMLEME amaçlı ince bir sarmalayıcı -- `run_research`'ün içinde kaybolan
    'ham arama sonucu sayısı'nı (SEARCH_RESULT_COUNT, madde 12) UAT raporuna taşımak
    için. Delegasyon dışında hiçbir davranış eklemez/değiştirmez."""

    def __init__(self, real_provider):
        self._real = real_provider
        self.calls = []

    def search(self, query, options=None):
        outcome = self._real.search(query, options)
        self.calls.append({"query": query, "result_count": len(outcome.results), "status": outcome.status})
        return outcome


def stage_research_engine(report, searxng_provider, fetcher=None):
    """`fetcher=None` (varsayılan): gerçek `SafeFetcher()` kurulur (madde 13 -- tam güvenlik
    kurallarıyla, GEVŞETİLMEDİ) -- gerçek PC çalıştırmasında davranış budur, hiç değişmez.
    Yalnızca bulut-taraflı mock testlerin (madde 29: 'mock fetch failure') sahte bir
    `.fetch(url) -> FetchOutcome` nesnesi enjekte edebilmesi için parametre eklendi --
    `research/engine.py::run_research`'ün ZATEN kullandığı AYNI dependency-injection
    deseni (madde 61: yeni bir desen İCAT EDİLMEDİ)."""
    stage = report.stage("F_research_engine")
    from research.fetcher import SafeFetcher
    from research.engine import run_research
    from research.models import SUPPORTED, FETCH_STATUSES_WITH_REAL_CONTENT

    fetcher = fetcher if fetcher is not None else SafeFetcher()
    results_by_question = {}
    real_result_objects = {}

    for qid, question in RESEARCH_QUESTIONS:
        wrapper = _CountingProviderWrapper(searxng_provider)
        entry = {"question": question}
        t0 = time.monotonic()
        try:
            result = run_research(question, wrapper, fetcher)
        except Exception as exc:  # noqa: BLE001
            # run_research madde 26 gereği raise etmemeli -- burada yakalanırsa bu
            # kendi başına bir BUG bulgusu, gizlenmeden raporlanır.
            entry["UNEXPECTED_EXCEPTION"] = repr(exc)
            entry["traceback"] = traceback.format_exc()
            report.note(f"[F] {qid}) BEKLENMEYEN İSTİSNA (run_research raise etti -- madde 26 ihlali): {exc!r}")
            results_by_question[qid] = entry
            continue

        real_result_objects[qid] = result
        search_result_count = sum(c["result_count"] for c in wrapper.calls)
        fetched_count = sum(1 for e in result.evidence if e.has_real_content())
        extracted_count = sum(1 for e in result.evidence if e.has_real_content() and e.passage)
        official_count = sum(1 for e in result.evidence if e.official)

        entry.update({
            "elapsed_seconds": round(time.monotonic() - t0, 3),
            "subquestions": list(result.subquestions),
            "queries": list(result.queries),
            "search_calls": wrapper.calls,
            "SEARCH_RESULT_COUNT": search_result_count,
            "FETCHED_COUNT": fetched_count,
            "EXTRACTED_COUNT": extracted_count,
            "EVIDENCE_COUNT": len(result.evidence),
            "official_evidence_count": official_count,
            "search_health": result.search_health,
            "status": result.status,
            "claims": [
                {"text": c.text, "value": c.value, "period": c.period, "status": c.status,
                 "supporting_evidence_ids": list(c.supporting_evidence_ids)}
                for c in result.claims
            ],
            "verified_claims_count": len(result.verified_claims),
            "conflicts": list(result.conflicts),
            "missing_information": list(result.missing_information),
            "sources": list(result.sources),
            "evidence_detail": [
                {"id": e.evidence_id, "url": e.url, "domain": e.domain, "source_type": e.source_type,
                 "official": e.official, "fetch_status": e.fetch_status, "period": e.period,
                 "has_real_content": e.has_real_content(), "passage_len": len(e.passage or "")}
                for e in result.evidence
            ],
        })
        results_by_question[qid] = entry
        report.note(
            f"[F] {qid}) '{question}' -> {result.status} | search={search_result_count} "
            f"fetch={fetched_count} extract={extracted_count} evidence={len(result.evidence)} "
            f"claims={len(result.claims)} verified={len(result.verified_claims)} "
            f"({entry['elapsed_seconds']}s)"
        )
        time.sleep(1.5)  # madde 8/burst korumasına saygı: sorular arası da bekleme

    stage["by_question"] = results_by_question

    total_fetched = sum(e.get("FETCHED_COUNT", 0) for e in results_by_question.values())
    total_extracted = sum(e.get("EXTRACTED_COUNT", 0) for e in results_by_question.values())
    total_search = sum(e.get("SEARCH_RESULT_COUNT", 0) for e in results_by_question.values())

    if total_search > 0:
        report.set_criterion(6, True, f"Research Engine gerçek SearchProvider ile {total_search} ham sonuç işledi")
    else:
        report.set_criterion(6, False, "Research Engine hiçbir gerçek arama sonucu işlemedi")

    if total_fetched > 0:
        report.set_criterion(7, True, f"{total_fetched} evidence FETCH_OK (gerçekten fetch edildi)")
    else:
        report.set_criterion(7, False, "Hiçbir URL gerçekten fetch edilemedi")

    if total_extracted > 0:
        report.set_criterion(8, True, f"{total_extracted} evidence gerçek extracted passage içeriyor")
    else:
        report.set_criterion(8, False, "Hiçbir evidence'ta extracted content yok")

    # madde 24-9: snippet-only asla verified claim olamaz -- bu zaten
    # ResearchResult.__post_init__ + Claim üretiminde YAPISAL olarak garanti (madde 36),
    # burada GERÇEK sonuçlar üzerinde gözlemsel olarak da doğrulanır.
    snippet_only_verified = False
    for entry in results_by_question.values():
        evid_by_id = {e["id"]: e for e in entry.get("evidence_detail", [])}
        for claim in entry.get("claims", []):
            if claim["status"] == SUPPORTED:
                supporting = [evid_by_id[i] for i in claim["supporting_evidence_ids"] if i in evid_by_id]
                if supporting and not any(s["has_real_content"] for s in supporting):
                    snippet_only_verified = True
    report.set_criterion(9, not snippet_only_verified,
                          "snippet-only kanıtla SUPPORTED üretilmedi" if not snippet_only_verified
                          else "BUG: snippet-only kanıt SUPPORTED üretti")

    stage["result"] = "OK"
    return stage, real_result_objects


# ---------------------------------------------------------------------------------
# AŞAMA G: SafeFetcher SSRF/robots koruması BOZULMADI mı (madde 13) -- ağdan bağımsız
# ---------------------------------------------------------------------------------

def stage_safe_fetcher_guard(report):
    stage = report.stage("G_safe_fetcher_guard")
    from research.fetcher import SafeFetcher
    from research.models import FETCH_BLOCKED_SSRF

    fetcher = SafeFetcher()
    checks = {}
    for label, url in (
        ("localhost", "http://localhost/kaizen-should-never-fetch-this"),
        ("127.0.0.1", f"{SEARXNG_BASE_URL}/kaizen-should-never-fetch-this"),
        ("private_ip", "http://10.0.0.5/kaizen-should-never-fetch-this"),
        ("file_scheme", "file:///etc/passwd"),
    ):
        try:
            outcome = fetcher.fetch(url)
            checks[label] = {"status": outcome.status, "blocked": outcome.status == FETCH_BLOCKED_SSRF
                              or outcome.status != "FETCH_OK"}
        except Exception as exc:  # noqa: BLE001
            checks[label] = {"exception": repr(exc), "blocked": True}

    all_blocked = all(c.get("blocked") for c in checks.values())
    stage["checks"] = checks
    stage["result"] = "OK" if all_blocked else "SECURITY_REGRESSION"
    if all_blocked:
        report.note("[G] SafeFetcher SSRF/localhost/file:// korumaları SAĞLAM (madde 13 gevşetilmedi).")
    else:
        report.note("[G] *** GÜVENLİK REGRESYONU: SafeFetcher bir tehlikeli URL'i engellemedi! ***")
    return stage


# ---------------------------------------------------------------------------------
# AŞAMA H: Consensus gerçekliği -- SUPPORTED ise NEDEN (madde 14)
# ---------------------------------------------------------------------------------

def stage_consensus_reality(report, real_results):
    stage = report.stage("H_consensus_reality")
    from research.models import SUPPORTED

    explanations = {}
    for qid, result in real_results.items():
        evid_by_id = {e.evidence_id: e for e in result.evidence}
        for claim in result.claims:
            if claim.status != SUPPORTED:
                continue
            supporting = [evid_by_id[i] for i in claim.supporting_evidence_ids if i in evid_by_id]
            official = [e for e in supporting if e.official]
            domains = sorted({e.domain for e in supporting})
            explanations.setdefault(qid, []).append({
                "claim": claim.text,
                "official_sources": [e.url for e in official],
                "distinct_domains": domains,
                "reason": (
                    "OFFICIAL kaynak + dönem uyumu" if official
                    else f"{len(domains)} BAĞIMSIZ (farklı domain) kaynağın uzlaşısı" if len(domains) >= 2
                    else "UYARI: ne official ne de 2+ bağımsız domain -- bu SUPPORTED şüpheli olmalı"
                ),
            })
    stage["explanations"] = explanations
    for qid, items in explanations.items():
        for item in items:
            report.note(f"[H] {qid}) SUPPORTED çünkü: {item['reason']} ({item['distinct_domains']})")
    if not explanations:
        report.note("[H] Bu çalıştırmada hiçbir claim SUPPORTED olmadı (raporlanacak consensus yok).")
    stage["result"] = "OK"
    return stage


# ---------------------------------------------------------------------------------
# AŞAMA I: Alakasız-ama-güvenilir kaynak adversarial testi (madde 15, RELEASE BLOCKER)
# ---------------------------------------------------------------------------------

def stage_relevance_adversarial(report, real_results):
    """madde 15: GERÇEK, bu çalıştırmada fetch edilmiş bir OFFICIAL/PROFESSIONAL evidence'ı
    alıp BAŞKA bir (konu olarak alakasız) soruya "kanıt" olarak besler -- sentetik pasaj
    UYDURULMAZ, gerçek fetch edilmiş pasaj kullanılır, yalnızca hangi alt-soruya
    bağlandığı değiştirilir (`dataclasses.replace`). Böylece GERÇEK verifier kodu
    (`research/verifier.py::_is_relevant`) gerçek veriyle adversarial test edilir."""
    stage = report.stage("I_relevance_adversarial")
    from research.models import Evidence, Subquestion, ResearchPlan
    from research.verifier import build_claims

    # En az iki farklı sorudan, gerçekten fetch edilmiş (has_real_content) evidence topla.
    real_evidence_by_qid = {}
    for qid, result in real_results.items():
        real = [e for e in result.evidence if e.has_real_content() and e.passage]
        if real:
            real_evidence_by_qid[qid] = real[0]

    if len(real_evidence_by_qid) < 2:
        stage["result"] = "SKIPPED_INSUFFICIENT_REAL_EVIDENCE"
        stage["detail"] = "En az 2 farklı sorudan gerçek içerikli evidence gerekli, bulunamadı."
        report.note("[I] Adversarial alaka testi ATLANDI (yeterli gerçek evidence yok bu çalıştırmada).")
        # UAT unit-regression'ının (tests/test_research_verifier.py) bu bug'ı zaten kapsadığını
        # hatırlat -- yaşayan kod korumasının canlı ortamda test EDİLEMEMESİ, korumanın
        # KENDİSİNİN olmadığı anlamına gelmez.
        report.note("[I] NOT: Bu koruma zaten tests/test_research_verifier.py::"
                     "test_build_claims_qualitative_irrelevant_official_source_never_supported "
                     "ile birim-test seviyesinde regresyona bağlanmıştır (bkz. madde 29 ön-kontrolleri).")
        return stage

    ids = list(real_evidence_by_qid.keys())
    victim_qid, donor_qid = ids[0], ids[1]
    donor_evidence = real_evidence_by_qid[donor_qid]
    victim_question = real_results[victim_qid].question

    # DİKKAT: donor_evidence'ın pasajı GERÇEK (gerçekten fetch edilmiş) ama victim_question
    # ile İÇERİK OLARAK alakasız olması BEKLENİR (farklı konu). Eğer tesadüfen alakalıysa
    # (örn. iki soru da örtüşen terimler içeriyorsa) test bunu da dürüstçe raporlar.
    cross_wired = dataclasses.replace(
        donor_evidence, evidence_id="uat_cross_wired", subquestion=victim_question,
    )
    plan = ResearchPlan(
        question=victim_question,
        subquestions=(Subquestion(text=victim_question, search_query=victim_question),),
        requested_period=None,
    )
    claims = build_claims(plan, {victim_question: [cross_wired]})
    supported = [c for c in claims if c.status == "SUPPORTED"]

    stage["victim_question"] = victim_question
    stage["donor_evidence_url"] = donor_evidence.url
    stage["donor_evidence_official"] = donor_evidence.official
    stage["donor_evidence_domain"] = donor_evidence.domain
    stage["produced_claims"] = [{"text": c.text, "status": c.status} for c in claims]

    if supported:
        stage["result"] = "RELEASE_BLOCKER_CONFIRMED"
        report.set_criterion(11, False,
                              f"ALAKASIZ kaynak (donor={donor_qid}) victim soruyu ({victim_qid}) SUPPORTED yaptı!")
        report.note("[I] *** RELEASE BLOCKER: alakasız-ama-güvenilir kaynak SUPPORTED üretti! ***")
    else:
        stage["result"] = "OK_REJECTED"
        report.set_criterion(11, True,
                              f"Çapraz-bağlı gerçek evidence (donor={donor_qid} -> victim={victim_qid}) "
                              f"SUPPORTED üretmedi (status'lar: {[c.status for c in claims] or 'claim yok'})")
        report.note(f"[I] OK: alakasız-ama-güvenilir gerçek kaynak (donor {donor_qid} -> victim {victim_qid}) "
                     f"SUPPORTED üretmedi.")
    return stage


# ---------------------------------------------------------------------------------
# AŞAMA J: Temporal + Conflict adversarial testleri (madde 16-17) -- gerçek evidence,
# kontrollü mutasyon
# ---------------------------------------------------------------------------------

def stage_temporal_and_conflict_adversarial(report, real_results):
    stage = report.stage("J_temporal_conflict_adversarial")
    from research.models import Subquestion, ResearchPlan
    from research.verifier import build_claims

    # --- Temporal: 2026 sorusuna GERÇEK bir evidence'ın URL/domain'ini al, ama pasajı
    # AÇIKÇA 2024 tarihli bir cümleyle değiştir (sentetik-ama-tutarlı) --------------------
    # ÖNEMLİ TASARIM NOTU (bu UAT'ı geliştirirken bizzat bulunan bir kendi-kendini-test
    # bulgusu): yalnızca `evidence.period` alanını mutasyona uğratmak (pasajı GERÇEK
    # bırakarak) GÜVENİLMEZ bir test üretir -- çünkü `accounting/facts.py::FactExtractor.
    # _year_for` pasaj METNİNDE geçen bir yıl literalini (varsa) `effective_year` alanına
    # göre HER ZAMAN önceliklendirir (bkz. `_YEAR.finditer`). Gerçek 2026 sorgusuna dönen
    # bir sayfanın pasajı genellikle zaten "2026" kelimesini içerdiğinden, yalnız
    # `period` alanını "2024"e çekmek metindeki "2026"yı ETKİSİZ BIRAKMAZ -- bu da yanlış-
    # pozitif bir "OK" (ya da yanlış-pozitif bir "BUG") gösterebilir, testi ANLAMSIZLAŞTIRIR.
    # Bu yüzden pasaj da AÇIKÇA 2024 tarihli, kendi içinde TUTARLI bir cümleyle değiştirilir
    # (URL/domain/official gerçek kanıttan kalır -- yalnızca pasaj sentetik, tıpkı aşağıdaki
    # conflict testindeki desenle AYNI).
    temporal_result = {}
    d_result = real_results.get("D")
    if d_result is not None:
        real_2026 = [e for e in d_result.evidence if e.has_real_content() and e.passage]
        if real_2026:
            evidence = real_2026[0]
            question = d_result.question
            downgraded = dataclasses.replace(
                evidence, evidence_id="uat_temporal_downgraded", period="2024",
                passage="2024 yeniden değerleme oranı yüzde 58,46 olarak Resmi Gazete'de yayımlanmıştır.",
            )
            plan = ResearchPlan(question=question, subquestions=(Subquestion(text=question, search_query=question),),
                                 requested_period="2026")
            claims = build_claims(plan, {question: [downgraded]})
            supported = [c for c in claims if c.status == "SUPPORTED"]
            temporal_result = {
                "question": question, "original_period": evidence.period, "downgraded_to": "2024",
                "requested_period": "2026", "produced_claims": [{"text": c.text, "status": c.status} for c in claims],
                "wrongly_supported": bool(supported),
            }
            report.set_criterion(10, not bool(supported),
                                  "2024 dönemli (tutarlı: hem period hem pasaj) kanıt 2026 talebini "
                                  "SUPPORTED yapmadı" if not supported
                                  else "BUG: yanlış dönem SUPPORTED üretti")
            report.note(f"[J] Temporal adversarial (D, 2024->2026 talebi): "
                        f"{'*** BUG: SUPPORTED üretti ***' if supported else 'OK, reddedildi'}")
        else:
            report.note("[J] Temporal adversarial ATLANDI: D sorusunda gerçek içerikli evidence yok.")
            report.set_criterion(10, None, "D sorusunda test edilecek gerçek evidence bulunamadı")
    else:
        report.set_criterion(10, None, "D sorusu hiç çalışmadı")
    stage["temporal"] = temporal_result

    # --- Conflict: aynı soruya iki FARKLI (bağımsız domainli) evidence, farklı pasaj ----
    conflict_result = {}
    if d_result is not None:
        real = [e for e in d_result.evidence if e.has_real_content() and e.passage]
        if real:
            base = real[0]
            question = d_result.question
            variant_a = dataclasses.replace(
                base, evidence_id="uat_conflict_a", domain="uat-kaynak-a.gov.tr",
                source_name="UAT Kaynak A", url="https://uat-kaynak-a.gov.tr/haber-a",
                passage="2026 yeniden değerleme oranı yüzde 25 olarak belirlenmiştir.",
                period="2026", official=True, source_type=base.source_type if base.source_type == "OFFICIAL" else "OFFICIAL",
            )
            variant_b = dataclasses.replace(
                base, evidence_id="uat_conflict_b", domain="uat-kaynak-b.gov.tr",
                source_name="UAT Kaynak B", url="https://uat-kaynak-b.gov.tr/haber-b",
                passage="2026 yeniden değerleme oranı yüzde 18 olarak açıklanmıştır.",
                period="2026", official=True, source_type=base.source_type if base.source_type == "OFFICIAL" else "OFFICIAL",
            )
            plan = ResearchPlan(question=question, subquestions=(Subquestion(text=question, search_query=question),),
                                 requested_period="2026")
            claims = build_claims(plan, {question: [variant_a, variant_b]})
            statuses = [c.status for c in claims]
            wrongly_supported = "SUPPORTED" in statuses
            conflict_result = {
                "question": question, "produced_claims": [{"text": c.text, "status": c.status} for c in claims],
                "wrongly_supported": wrongly_supported,
            }
            report.set_criterion(12, not wrongly_supported,
                                  "iki çelişen değer SUPPORTED üretmedi (CONFLICTED/INSUFFICIENT/PARTIAL bekleniyordu)"
                                  if not wrongly_supported else
                                  "BUG: iki çelişen sayısal değer SUPPORTED üretti")
            report.note(f"[J] Conflict adversarial (D, %25 vs %18): statuses={statuses} "
                        f"{'*** BUG ***' if wrongly_supported else 'OK'}")
        else:
            report.note("[J] Conflict adversarial ATLANDI: D sorusunda gerçek içerikli evidence yok.")
            report.set_criterion(12, None, "D sorusunda test edilecek gerçek evidence bulunamadı")
    else:
        report.set_criterion(12, None, "D sorusu hiç çalışmadı")
    stage["conflict"] = conflict_result
    return stage


# ---------------------------------------------------------------------------------
# AŞAMA K: KaizenBrain shadow A/B testi (madde 18-21) -- gerçek data/'ya DOKUNMAZ
# ---------------------------------------------------------------------------------

def _build_isolated_brain(research_engine_enabled, search_provider, temp_dir):
    """Build a shadow brain with isolated stores and logs; runtime config is read only."""
    from config.config_manager import ConfigManager
    from core.ai.provider_factory import build_provider
    from core.ai.provider_manager import ProviderManager
    from accounting.accounting_agent import AccountingAgent
    from accounting.facts import FactRegistry
    from accounting.site_store import SiteStore
    from core.kaizen_brain import KaizenBrain
    from memory.brain_manager import BrainManager
    from memory.knowledge_cards import KnowledgeCardStore
    from memory.learning_store import LearningStore

    config = ConfigManager()  # yalnız OKUNUR (model.provider vb.) -- hiç YAZILMAZ
    provider_manager = ProviderManager()
    # UAT bulgusu (2026-09-24, ilk gerçek PC koşusu): build_provider() eskiden log_dir hiç
    # ALMIYORDU, bu yüzden HermesProvider() -> HermesBridge() HER ZAMAN gerçek
    # logs/kaizen.log'a yazardı -- madde 23 ihlali. Düzeltildi (core/ai/provider_factory.py
    # ::build_provider log_dir=None eklendi, geriye dönük uyumlu); burada GERÇEK data/logs/
    # yerine izole temp_dir kullanılır.
    provider_manager.set_provider(build_provider(config, log_dir=str(temp_dir / "logs")))
    accounting_agent = AccountingAgent(
        provider_manager.provider,
        learning_memory_path=temp_dir / "accounting_learning.json",
    )
    learning_store = LearningStore(db_path=temp_dir / "kaizen_learning.sqlite3")
    site_store = SiteStore(db_path=temp_dir / "accounting_knowledge.sqlite3")
    facts = FactRegistry(site_store.db_path)
    cards = KnowledgeCardStore(learning_store.db_path)
    brain_manager = BrainManager(
        learning_store=learning_store, site_store=site_store, facts=facts, cards=cards,
        exam_candidates_path=temp_dir / "auto_exam_candidates.jsonl",
        log_dir=str(temp_dir / "logs"),
    )

    return KaizenBrain(
        provider_manager, accounting_agent, brain_manager=brain_manager,
        principle_retriever=None, learning_brain_enabled=False,
        search_provider=search_provider, research_engine_enabled=research_engine_enabled,
    )


class _EmptySearchProviderForFallbackCheck:
    """`search/provider.py::SearchProvider` Protocol'üne (yalnız `.search()` zorunlu) birebir
    uyan, HER ZAMAN boş/yetersiz sonuç döndüren minimal bir sağlayıcı.

    NEDEN VAR (2026-09-25 UAT bulgusu, kullanıcının GERÇEK PC'sinde bulunan bir GATE
    MANTIĞI hatası -- 'PermissionError' ile aynı koşuda değil, kullanıcının bu koşudan
    SONRAKİ talimatında istenen '4. PARTIAL'a neden olan tüm gate kriterlerini incele'
    talebi üzerine bulundu): eski kodda kriter 15 ('research yetersiz olduğunda mevcut
    fallback güvenli kalıyor') SADECE `on_via == 'hermes'` dalında set ediliyordu --
    `on_via == 'engine'` dalında (yani Research Engine GERÇEKTEN bir SUPPORTED cevap
    bulduğunda -- sistemin en iyi performans gösterdiği durum) kriter 15 HİÇ set
    edilmiyordu ve `None` kalıyordu. Sonuç: gerçek arama altyapısı MÜKEMMEL çalışsa bile
    UAT ASLA PASS olamıyordu -- bu, sistemin bir eksikliği değil, UAT GATE MANTIĞININ
    KENDİ hatasıydı.

    Düzeltme: kriter 15'in gerçek iddiasını ('araştırma yetersiz kaldığında KaizenBrain
    GÜVENLE Hermes'e düşer'), canlı bir sorgunun TESADÜFEN yetersiz sonuç vermesine
    bağlı kalmadan, DETERMİNİSTİK olarak kanıtlayan AYRI ve HER ZAMAN çalışan üçüncü bir
    kontrol eklendi (bkz. `stage_kaizenbrain_shadow` içindeki `tmp_c` bloğu). Bu sınıf o
    kontrolün girdisidir: gerçek `KaizenBrain`/`BrainManager`/Hermes zinciri hiç
    mock'LANMAZ -- yalnızca ARAMA KATMANI'nın (search != research, madde 16) 'hiçbir
    zaman sonuç bulamıyor' senaryosu kontrollü biçimde üretilir. Bu, `stage_research_engine`
    içindeki `_CountingProviderWrapper`'ın kullandığı AYNI dependency-injection deseninin
    (yeni bir mekanizma İCAT EDİLMEDİ) bir başka uygulamasıdır."""

    def search(self, query, options=None):
        from search.provider import STATUS_EMPTY, SearchOutcome
        return SearchOutcome(results=(), query=query, status=STATUS_EMPTY)


def stage_kaizenbrain_shadow(report, searxng_provider):
    stage = report.stage("K_kaizenbrain_shadow")
    ab_results = {}
    with tempfile.TemporaryDirectory(prefix="kaizen_uat_off_") as tmp_off, \
         tempfile.TemporaryDirectory(prefix="kaizen_uat_on_") as tmp_on, \
         tempfile.TemporaryDirectory(prefix="kaizen_uat_insufficient_") as tmp_c:
        try:
            brain_off = _build_isolated_brain(False, None, Path(tmp_off))
            brain_on = _build_isolated_brain(True, searxng_provider, Path(tmp_on))
            # Kriter 15'in kendi ADANMIŞ, deterministik kontrolü için üçüncü bir izole
            # shadow brain -- gerçek `searxng_provider` durumundan (Docker/network
            # erişilebilir mi vb.) TAMAMEN bağımsız, HER ZAMAN kurulabilir/çalıştırılabilir.
            brain_insufficient = _build_isolated_brain(
                True, _EmptySearchProviderForFallbackCheck(), Path(tmp_c)
            )
        except Exception as exc:  # noqa: BLE001
            stage["result"] = "SETUP_FAILED"
            stage["detail"] = f"{exc!r}\n{traceback.format_exc()}"
            report.note(f"[K] KaizenBrain shadow kurulumu başarısız: {exc!r}")
            return stage

        # madde 19: OFF, bir soruda test edilir -- mevcut davranış birebir korunmalı,
        # yani _research_engine_once HİÇ çağrılmamalı (research_engine_enabled=False
        # zaten bunu kod seviyesinde garanti eder -- burada GÖZLEMSEL olarak doğrulanır).
        off_question = RESEARCH_QUESTIONS[0][1]
        (off_answer, off_err) = _run_with_timeout(brain_off.answer, BRAIN_TIMEOUT_SECONDS, off_question)
        ab_results["OFF"] = {
            "question": off_question,
            "error": off_err,
            "answer_present": bool(off_answer),
            "last_route": brain_off.last_route,
            "last_research_via": brain_off._last_research_via,
        }
        report.note(f"[K] OFF: last_research_via={brain_off._last_research_via!r} "
                    f"route={brain_off.last_route!r} err={off_err!r}")

        # madde 20: ON, GÜNCEL/araştırma gerektiren bir soruda test edilir.
        on_question = RESEARCH_QUESTIONS[0][1]  # "2026 gelir vergisi tarifesi nedir?" -- CURRENT_TERMS'e uyar
        (on_answer, on_err) = _run_with_timeout(brain_on.answer, BRAIN_TIMEOUT_SECONDS, on_question)
        ab_results["ON"] = {
            "question": on_question,
            "error": on_err,
            "answer_present": bool(on_answer),
            "last_route": brain_on.last_route,
            "last_research_via": brain_on._last_research_via,
        }
        report.note(f"[K] ON:  last_research_via={brain_on._last_research_via!r} "
                    f"route={brain_on.last_route!r} err={on_err!r}")

        # Kriter 15'in ADANMIŞ, deterministik kontrolü: arama katmanı HER ZAMAN boş dönerse
        # (bkz. _EmptySearchProviderForFallbackCheck) KaizenBrain -- research_engine_enabled
        # AÇIK olsa bile -- GÜVENLE Hermes'e düşmeli ve yine de gerçek/kullanılabilir bir
        # cevap vermeli (çökmemeli, boş dönmemeli).
        insufficient_question = RESEARCH_QUESTIONS[0][1]
        (insufficient_answer, insufficient_err) = _run_with_timeout(
            brain_insufficient.answer, BRAIN_TIMEOUT_SECONDS, insufficient_question
        )
        ab_results["INSUFFICIENT_CHECK"] = {
            "question": insufficient_question,
            "error": insufficient_err,
            "answer_present": bool(insufficient_answer),
            "last_route": brain_insufficient.last_route,
            "last_research_via": brain_insufficient._last_research_via,
        }
        report.note(f"[K] INSUFFICIENT_CHECK: last_research_via={brain_insufficient._last_research_via!r} "
                    f"route={brain_insufficient.last_route!r} err={insufficient_err!r}")

        # Keep the lifecycle hook before removing the isolated stores.
        shutdown_results = {}
        for label, brain in (("OFF", brain_off), ("ON", brain_on), ("INSUFFICIENT_CHECK", brain_insufficient)):
            try:
                completed = brain.brain.shutdown(timeout=10.0)
                shutdown_results[label] = {"completed": bool(completed)}
                if completed:
                    report.note(f"[K] {label}: BrainManager.shutdown() OK -- tüm worker'lar "
                                 "gerçekten bitti (tempdir güvenle silinebilir).")
                else:
                    report.note(f"[K] {label}: *** BrainManager.shutdown() timeout içinde TÜM "
                                 "worker'ların bittiğini doğrulayamadı -- olası kaynak sızıntısı, "
                                 "raporda işaretlendi. ***")
            except Exception as exc:  # noqa: BLE001
                # shutdown() kendisi zaten istisna sızdırmamalı (bkz. BrainManager.shutdown
                # docstring) -- ama madde 26 disiplini gereği burada da savunma amaçlı sarılır.
                shutdown_results[label] = {"completed": False, "exception": repr(exc)}
                report.note(f"[K] {label}: BrainManager.shutdown() sırasında beklenmeyen istisna: {exc!r}")
        stage["shutdown_results"] = shutdown_results

    stage["ab_results"] = ab_results

    on_via = ab_results["ON"]["last_research_via"]
    if on_via == "engine":
        report.set_criterion(13, True, "ON modunda _last_research_via=='engine' -- Research Engine gerçekten çağrıldı")
        report.set_criterion(14, True, "Research Engine SUPPORTED bulduğu için Hermes fallback ATLANDI")
        report.note("[K] ON: Research Engine SUPPORTED buldu, Hermes fallback KULLANILMADI.")
    elif on_via == "hermes":
        # Research Engine denendi (giriş yaptı) ama SUPPORTED üretemedi -> Hermes fallback.
        # "Research Engine'e GERÇEKTEN girdi mi" ayrı bir gözlem gerektirir: _research_engine_once
        # bir sonuç None dönmüşse _last_research_via zaten "hermes" olur, bu durumda kriter 13'ü
        # doğrudan ab_results'tan değil, F aşamasındaki gerçek run_research çağrılarından
        # (kriter 6) devralırız -- KaizenBrain seviyesinde ayrıca doğrulamak için debug bayrağı
        # yok, bu yüzden dürüstçe PARTIAL/N/A bırakılır, UYDURULMAZ.
        report.set_criterion(13, None,
                              "ON modunda Hermes'e düştü (Research Engine SUPPORTED bulamadı) -- "
                              "Research Engine'in GİRİŞ yaptığı F aşamasında (kriter 6) ayrıca kanıtlanmıştır")
        report.note("[K] ON: Research Engine SUPPORTED bulamadı, güvenle Hermes fallback'e düştü.")
    else:
        report.set_criterion(13, False, f"beklenmeyen last_research_via={on_via!r}")
        report.note(f"[K] BEKLENMEYEN last_research_via={on_via!r}")

    # DÜZELTME (2026-09-25, kullanıcının real-PC PARTIAL raporunun kök nedeni): kriter 15
    # artık ESKİDEN OLDUĞU GİBİ yalnızca `on_via == 'hermes'` dalına BAĞIMLI DEĞİL -- bu,
    # Research Engine gerçekten SUPPORTED bulduğunda (on_via=='engine', sistemin EN İYİ
    # performansı) kriter 15'in HİÇ set edilmeyip `None` kalmasına ve UAT'ın bu YÜZDEN asla
    # PASS olamamasına yol açıyordu (gerçek bir sistem eksikliği DEĞİL, gate mantığı hatası).
    # Artık kriter 15, YUKARIDAKİ `INSUFFICIENT_CHECK` bloğunun (HER ZAMAN, searxng/Docker
    # durumundan bağımsız çalışan, deterministik 'arama hep boş dönerse ne olur' testi)
    # SONUCUNA göre AYRI ve KOŞULSUZ olarak belirlenir.
    insufficient_via = ab_results["INSUFFICIENT_CHECK"]["last_research_via"]
    insufficient_answer_present = ab_results["INSUFFICIENT_CHECK"]["answer_present"]
    if insufficient_via == "hermes" and insufficient_answer_present:
        report.set_criterion(
            15, True,
            "Arama katmanı HER ZAMAN boş sonuç dönerken (deterministik kontrol) KaizenBrain "
            "güvenle Hermes'e düştü VE gerçek/kullanılabilir bir cevap üretti",
        )
        report.note("[K] INSUFFICIENT_CHECK: OK -- araştırma yetersiz kaldığında Hermes fallback güvenli.")
    elif insufficient_via == "engine":
        report.set_criterion(
            15, False,
            "*** CİDDİ BULGU: arama katmanı HİÇBİR sonuç döndürmediği halde "
            "_last_research_via=='engine' oldu (Research Engine boş kanıttan SUPPORTED üretmiş "
            "olabilir) ***",
        )
        report.note("[K] *** INSUFFICIENT_CHECK: BEKLENMEYEN -- boş aramada 'engine' yolu kullanıldı! ***")
    else:
        report.set_criterion(
            15, False,
            f"INSUFFICIENT_CHECK beklenen güvenli davranışı göstermedi: "
            f"last_research_via={insufficient_via!r} answer_present={insufficient_answer_present!r} "
            f"err={ab_results['INSUFFICIENT_CHECK']['error']!r}",
        )
        report.note(f"[K] INSUFFICIENT_CHECK BAŞARISIZ: last_research_via={insufficient_via!r} "
                     f"answer_present={insufficient_answer_present!r}")

    if ab_results["OFF"]["last_research_via"] == "engine":
        report.note("[K] *** BUG: OFF modunda research_engine_enabled=False iken Research Engine çağrıldı! ***")
    else:
        report.note("[K] OFF: Research Engine hiç çağrılmadı (mevcut davranış korunuyor) -- doğrulandı.")

    stage["result"] = "OK"
    return stage


# ---------------------------------------------------------------------------------
# SHA256 bütünlük -- pre/post karşılaştırma + kriter 16 kararı
# ---------------------------------------------------------------------------------
# UAT bulgusu (2026-09-24, kullanıcının yeni talimatı): bir dosya hash'lenemediğinde
# script ASLA "bütünlük doğrulandı" DEMEMELİ -- sonuç INTEGRITY_PARTIAL olmalı, ve
# GUARDED_DIRS'in TAMAMI (data/knowledge/memory/logs) zaten "korunan kullanıcı verisi"
# olduğu için (yalnız bu dizinler taranıyor, madde 23), hash'lenemeyen HER girdi bu
# korunan veri içindedir -- dolayısıyla PASS kapısı kriter 16'yı asla TRUE yapamaz.

_INTEGRITY_VERIFIED = "VERIFIED"
_INTEGRITY_PARTIAL = "INTEGRITY_PARTIAL"
_INTEGRITY_MUTATED = "MUTATED"


def _finalize_integrity(report, pre_hashes, pre_skipped, post_hashes, post_skipped):
    sha_diff = {
        k: (pre_hashes.get(k), post_hashes.get(k))
        for k in set(pre_hashes) | set(post_hashes)
        if pre_hashes.get(k) != post_hashes.get(k)
    }
    stage = report.stage("Z_sha_integrity")
    stage["pre_file_count"] = len(pre_hashes)
    stage["post_file_count"] = len(post_hashes)
    stage["pre_skipped_count"] = len(pre_skipped)
    stage["post_skipped_count"] = len(post_skipped)
    stage["pre_skipped"] = pre_skipped
    stage["post_skipped"] = post_skipped
    stage["changed_files"] = list(sha_diff.keys())
    stage["changed_files_detail"] = sha_diff

    all_skips = pre_skipped + post_skipped
    has_skips = bool(all_skips)
    has_diff = bool(sha_diff)

    if has_diff:
        stage["integrity_status"] = _INTEGRITY_MUTATED
        extra = f" (ayrıca {len(all_skips)} girdi hiç hash'lenemedi)" if has_skips else ""
        report.set_criterion(
            16, False,
            f"MUTATED: {len(sha_diff)} dosya değişti: {list(sha_diff.keys())[:10]}{extra}",
        )
        report.note(f"[Z] *** UYARI: data/knowledge/memory/logs içinde {len(sha_diff)} dosya "
                     f"değişti! (MUTATED) *** değişen dosyalar: {list(sha_diff.keys())[:10]}")
    elif has_skips:
        stage["integrity_status"] = _INTEGRITY_PARTIAL
        detail = "; ".join(f"{s['path']} [{s['classification']}]" for s in all_skips[:10])
        report.set_criterion(
            16, False,
            f"INTEGRITY_PARTIAL: {len(pre_hashes)} dosya hash'lendi ve DEĞİŞMEDİ, ama "
            f"{len(all_skips)} girdi hiç hash'lenemediği için 'bütünlük doğrulandı' DENEMEZ "
            f"(korunan dizinler içindeler): {detail}",
        )
        report.note(f"[Z] INTEGRITY_PARTIAL -- {len(pre_hashes)} dosya SHA256 olarak değişmedi, "
                     f"ama {len(all_skips)} girdi hash'lenemediği için tam bütünlük İDDİA EDİLMİYOR.")
        for s in all_skips[:20]:
            report.note(f"    [Z] SKIPPED [{s['classification']}] {s['path']} ({s['type']}) -- {s['detail']}")
    else:
        stage["integrity_status"] = _INTEGRITY_VERIFIED
        report.set_criterion(16, True, f"VERIFIED: {len(pre_hashes)} dosya SHA256 olarak değişmeden kaldı, 0 skip")
        report.note(f"[Z] SHA256 bütünlüğü TAM DOĞRULANDI (VERIFIED) -- {len(pre_hashes)} dosya "
                     "değişmedi, hiçbir girdi atlanmadı.")

    return stage["integrity_status"]


# ---------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------

def _run_main_body(report):
    """Tüm UAT akışını çalıştırır. Kasıtlı olarak `main()`'den AYRI tutulur: `main()`
    bunu tek bir try/except ile sarar ki (yeni talimat madde 7) `_run_main_body`
    içinde HERHANGİ bir yerde -- bir aşamanın try/except'i bile yakalamadığı, gerçekten
    beklenmeyen bir istisna (ör. Report/`_sha_snapshot` altyapısının kendisinde bir hata)
    -- oluşsa bile `main()` yine de TAM bir failure report yazabilsin. Her aşamadan önce
    `report.mark(...)` çağrılır ki böyle bir istisna durumunda hangi aşamada olunduğu
    `report.fatal['fatal_stage']`'e doğru yazılsın."""
    report.note(f"KAIZEN Research Engine UAT başlıyor -- {report.started_at}")
    report.note(f"Proje kökü: {ROOT}")

    report.mark("pre_sha_snapshot")
    pre_hashes, pre_skipped = _sha_snapshot()
    if pre_skipped:
        report.note(f"[pre] SHA ön-tarama: {len(pre_skipped)} girdi hash'lenemedi (bkz. Z_sha_integrity.pre_skipped).")

    report.mark("A_docker")
    docker_stage = None
    try:
        docker_stage = stage_docker(report)
    except Exception as exc:  # noqa: BLE001
        report.note(f"[A] Beklenmeyen istisna: {exc!r}\n{traceback.format_exc()}")

    docker_ok = bool(docker_stage and docker_stage.get("result") == "OK")

    searxng_provider = None
    real_results = {}

    if not docker_ok:
        report.note("[!] Docker/SearXNG container hazır değil -- internet'e bağımlı aşamalar "
                     "(B,C,D,E,F,H,I,J) ATLANIYOR. Sebep gizlenmedi, madde 4/25 gereği durduruldu.")
        for cid in (3, 4, 5, 6, 7, 8):
            report.set_criterion(cid, None, "Docker/SearXNG erişilemediği için test edilemedi")
    else:
        report.mark("B_http")
        try:
            stage_http(report)
        except Exception as exc:  # noqa: BLE001
            report.note(f"[B] Beklenmeyen istisna: {exc!r}")
        report.mark("C_json_api")
        try:
            stage_json_api(report)
        except Exception as exc:  # noqa: BLE001
            report.note(f"[C] Beklenmeyen istisna: {exc!r}")
        report.mark("D_engine_health")
        try:
            stage_engine_health(report)
        except Exception as exc:  # noqa: BLE001
            report.note(f"[D] Beklenmeyen istisna: {exc!r}")
        report.mark("E_searxng_provider")
        try:
            _e_stage, searxng_provider = stage_searxng_provider(report)
        except Exception as exc:  # noqa: BLE001
            report.note(f"[E] Beklenmeyen istisna: {exc!r}\n{traceback.format_exc()}")

        if searxng_provider is not None:
            report.mark("F_research_engine")
            try:
                _f_stage, real_results = stage_research_engine(report, searxng_provider)
            except Exception as exc:  # noqa: BLE001
                report.note(f"[F] Beklenmeyen istisna: {exc!r}\n{traceback.format_exc()}")

    # G: ağdan bağımsız, HER ZAMAN çalışır (madde 13 -- güvenlik gevşetilmedi kanıtı).
    report.mark("G_safe_fetcher_guard")
    try:
        stage_safe_fetcher_guard(report)
    except Exception as exc:  # noqa: BLE001
        report.note(f"[G] Beklenmeyen istisna: {exc!r}")

    if real_results:
        report.mark("H_consensus_reality")
        try:
            stage_consensus_reality(report, real_results)
        except Exception as exc:  # noqa: BLE001
            report.note(f"[H] Beklenmeyen istisna: {exc!r}")
        report.mark("I_relevance_adversarial")
        try:
            stage_relevance_adversarial(report, real_results)
        except Exception as exc:  # noqa: BLE001
            report.note(f"[I] Beklenmeyen istisna: {exc!r}\n{traceback.format_exc()}")
        report.mark("J_temporal_conflict_adversarial")
        try:
            stage_temporal_and_conflict_adversarial(report, real_results)
        except Exception as exc:  # noqa: BLE001
            report.note(f"[J] Beklenmeyen istisna: {exc!r}\n{traceback.format_exc()}")
    else:
        for cid in (10, 11, 12):
            report.set_criterion(cid, None, "F aşaması gerçek evidence üretmediği için test edilemedi")

    # K: KaizenBrain shadow -- ON varyantı searxng_provider None olsa bile GÜVENLE
    # fallback davranışını gösterdiği için (Research Engine SearXNG'siz de çökmez,
    # madde 26) yine de çalıştırılır; None ise ON kolu doğal olarak Hermes'e düşer.
    report.mark("K_kaizenbrain_shadow")
    try:
        stage_kaizenbrain_shadow(report, searxng_provider)
    except Exception as exc:  # noqa: BLE001
        report.note(f"[K] Beklenmeyen istisna: {exc!r}\n{traceback.format_exc()}")
        for cid in (13, 14, 15):
            if report.criteria[cid]["passed"] is None:
                report.set_criterion(cid, False, f"KaizenBrain shadow testi çöktü: {exc!r}")

    report.mark("post_sha_snapshot")
    post_hashes, post_skipped = _sha_snapshot()
    _finalize_integrity(report, pre_hashes, pre_skipped, post_hashes, post_skipped)

    report.mark("finalize_gate")


def main():
    report = Report()
    try:
        _run_main_body(report)
    except Exception as exc:  # noqa: BLE001
        # Yeni talimat madde 7: bir aşamanın KENDİ try/except'inin bile yakalamadığı,
        # gerçekten beklenmeyen bir istisna olsa dahi (ör. Report/SHA altyapısının
        # kendisinde bir hata) rapor dosyaları YİNE DE TAM yazılmalı -- fatal_stage,
        # exception_type, message (tam traceback konsola + JSON'a, madde 7'nin izin
        # verdiği gibi yalnız console/JSON'da, txt özetinde kısa hali).
        tb = traceback.format_exc()
        report.fatal = {
            "fatal_stage": report.current_stage_label,
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "traceback": tb,
        }
        report.note(f"*** UAT SCRIPT'İ BEKLENMEYEN BİR İSTİSNAYLA DURDU (aşama: "
                     f"{report.current_stage_label}): {type(exc).__name__}: {exc} ***")
        print(tb, file=sys.stderr)

    gate = report.finalize_gate()
    if report.fatal is not None and gate == "PASS":
        # Script'in kendisi beklenmedik biçimde durduysa, kalan kriterlerin hepsi
        # tesadüfen True olsa bile ASLA temiz PASS iddia edilmez (madde 10'un ruhu).
        gate = report.gate_result = "FAIL"
        report.note("[!] fatal hata mevcutken PASS iddia edilemez -- sonuç FAIL'e zorlandı.")

    report.note(f"=== UAT SONUCU: {gate} ===")
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
        # Buraya kadar gelmesi, main()'in KENDİSİNİN (Report() kurulumu ya da
        # write_files() gibi rapor-yazma altyapısının) çöktüğü anlamına gelir --
        # o durumda dosyaya hiçbir şey yazılamamış olabilir, bu yüzden tam
        # traceback en azından konsola basılır.
        print("UAT SCRIPT'İ BEKLENMEYEN BİR ŞEKİLDE ÇÖKTÜ (rapor dosyaya yazılamamış olabilir):",
              file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
