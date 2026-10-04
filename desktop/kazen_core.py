"""KAİZEN Desktop -- çerçeveden bağımsız (tkinter'sız) saf mantık katmanı.

Bu modül YENİ bir cevap motoru DEĞİLDİR: UI mesajı `KaizenEngine.cevap_ver()`'e iletir, geri
dönen metni ve `brain.last_trace`'i yalnız GÖSTERİM için ayrıştırır. Doğrulama kararını UI
vermez; yalnız backend'in trace alanlarını (research_status, consensus_status, ...) etiketler.

Dosya ekleme: UI dosyanın GERÇEK yerel yolunu mesaja tırnaklı olarak ekler; böylece mevcut
Document Engine (`documents/router.py::extract_document_path`) yolu kendisi bulur -- ayrı bir
belge yolu YOKTUR ve kullanıcıdan tekrar dosya yolu istenmez.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

APP_NAME = "KAİZEN"

# --- Modlar: bugün yalnız MUHASEBE aktif; GENEL AI için yalnız yer hazır (ikinci AI kurulmaz) ----
MODE_ACCOUNTING = "accounting"
MODE_GENERAL = "general"
MODES = {
    MODE_ACCOUNTING: {"label": "Muhasebe", "enabled": True},
    MODE_GENERAL: {"label": "Genel AI — Yakında", "enabled": False},   # feature flag: enabled=True yapılınca açılır
}
DEFAULT_MODE = MODE_ACCOUNTING


def mode_enabled(mode):
    return bool(MODES.get(mode, {}).get("enabled"))


# --- Dosya ekleme ------------------------------------------------------------------------------
try:  # Document Engine'in GERÇEK desteklediği biçimler (kopya liste tutulmaz)
    from documents.ops import SUPPORTED_READ_SUFFIXES
except Exception:  # pragma: no cover -- belge motoru yüklenemezse UI yine açılır
    SUPPORTED_READ_SUFFIXES = (".pdf", ".docx", ".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".md", ".json",
                               ".jpg", ".jpeg", ".png")
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class AttachmentCheck:
    ok: bool
    path: str
    name: str
    error: str = ""


def validate_attachment(path):
    """Açık hata döner; desteklenmeyen dosya ASLA sessizce yok sayılmaz."""
    p = Path(str(path).strip().strip('"'))
    name = p.name or str(path)
    if not p.exists():
        return AttachmentCheck(False, str(p), name, f"Dosya bulunamadı: {name}")
    if not p.is_file():
        return AttachmentCheck(False, str(p), name, f"Klasör eklenemez, bir dosya seçin: {name}")
    suffix = p.suffix.lower()
    if suffix not in SUPPORTED_READ_SUFFIXES:
        shown = ", ".join(s.lstrip(".").upper() for s in SUPPORTED_READ_SUFFIXES)
        return AttachmentCheck(False, str(p), name,
                               f"Desteklenmeyen dosya türü ({suffix or 'uzantısız'}): {name}. Desteklenenler: {shown}")
    try:
        size = p.stat().st_size
    except OSError as exc:
        return AttachmentCheck(False, str(p), name, f"Dosya okunamadı: {name} ({type(exc).__name__})")
    if size == 0:
        return AttachmentCheck(False, str(p), name, f"Dosya boş: {name}")
    if size > MAX_ATTACHMENT_BYTES:
        return AttachmentCheck(False, str(p), name, f"Dosya çok büyük (en fazla 50 MB): {name}")
    return AttachmentCheck(True, str(p.resolve()), name)


_FILE_REFERENCE_PHRASES = (
    "bu fatura", "bu dosya", "bu belge", "bu excel", "bu pdf", "bu tablo", "bu görsel", "bu gorsel",
    "faturayı", "faturayi", "dosyayı", "dosyayi", "belgeyi", "excel'deki", "excel’deki", "excel deki",
    "dosyadaki", "belgedeki", "faturadaki", "ekteki", "yüklediğim", "yukledigim", "eklediğim", "ekledigim",
)
_PATH_IN_TEXT = re.compile(r"[A-Za-z]:\\|\.(?:pdf|docx|xlsx|xlsm|xls|csv|txt|md|json|jpg|jpeg|png)\b", re.IGNORECASE)


def refers_to_attached_file(text):
    low = (text or "").lower()
    return any(phrase in low for phrase in _FILE_REFERENCE_PHRASES)


def compose_message(text, new_attachments=(), previous_attachments=()):
    """(engine_message, used_attachments). Yeni eklenen dosya her zaman mesaja bağlanır; önceki
    turda eklenmiş dosya, kullanıcı 'bu fatura/bu Excel' diye ona atıf yapıyorsa yeniden bağlanır
    (dosya yolu tekrar sorulmaz). Yol, Document Engine'in tanıdığı TIRNAKLI biçimde eklenir."""
    text = (text or "").strip()
    used = [a for a in new_attachments]
    if not used and previous_attachments and refers_to_attached_file(text) and not _PATH_IN_TEXT.search(text):
        used = [previous_attachments[-1]]
    if not used:
        return text, []
    if not text:
        text = "Bu dosyayı oku"
    refs = " ".join(f'"{a}"' for a in used)
    return f"{text} {refs}", used


def file_icon(path):
    suffix = Path(str(path)).suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".xls", ".csv"):
        return "📊"
    if suffix in (".jpg", ".jpeg", ".png"):
        return "🖼"
    return "📄"


# --- Cevap ayrıştırma (yalnız GÖSTERİM) -------------------------------------------------------------
_SOURCE_HEADERS = ("KAYNAKLAR", "KAYNAK")
_URL = re.compile(r"https?://[^\s;|)\]]+")
_OUTPUT_LINE = re.compile(r"^\s*ÇIKTI DOSYASI:\s*(.+?)(?:\s+\(orijinal.*)?$", re.IGNORECASE)
_ABS_FILE = re.compile(r'[A-Za-z]:\\[^\s"\'<>|?*]+?\.(?:xlsx|xlsm|xls|csv|docx|pdf|txt|json|md)', re.IGNORECASE)

_RESEARCH_STATUS_TR = {
    "SUPPORTED": "destekli", "PARTIAL": "kısmen destekli", "CONFLICTED": "çelişkili kaynaklar",
    "INSUFFICIENT": "yetersiz kanıt", "SEARCH_DEGRADED": "arama zayıf", "SEARCH_UNAVAILABLE": "arama yok",
}


@dataclass
class SourceItem:
    label: str
    url: str = ""


@dataclass
class AnswerView:
    body: str
    sources: list = field(default_factory=list)          # SourceItem
    verification: str = ""                               # backend'in söylediği doğrulama cümlesi / trace özeti
    route_label: str = ""
    outputs: list = field(default_factory=list)          # mevcut çıktı dosya yolları
    research_used: bool = False
    is_refusal: bool = False
    trace_summary: dict = field(default_factory=dict)    # SIR YOK: yalnız sayaç/durum


def _source_label(url):
    host = (urlparse(url).hostname or url).lower()
    try:
        from accounting.source_registry import trusted_source_for_url
        known = trusted_source_for_url(url)
        if known is not None:
            return known.name
    except Exception:
        pass
    return host.removeprefix("www.")


def _split_sources(lines):
    """KAYNAKLAR/KAYNAK bloklarını gövdeden ayırır. -> (gövde_satırları, [SourceItem], doğrulama_satırı)."""
    body, sources, verification = [], [], ""
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        head = stripped.split(":", 1)[0].strip().upper() if ":" in stripped else ""
        if head in _SOURCE_HEADERS:
            rest = stripped.split(":", 1)[1].strip()
            entries = []
            if rest:
                entries.extend(part.strip() for part in re.split(r"\s;\s", rest) if part.strip())
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith(("-", "•", "▸", "*")):
                entries.append(lines[j].strip().lstrip("-•▸* ").strip())
                j += 1
            for entry in entries:
                url = _URL.search(entry)
                if url:
                    sources.append(SourceItem(_source_label(url.group(0)), url.group(0)))
                else:
                    sources.append(SourceItem(entry))
            i = j
            continue
        if stripped.upper().startswith("DOĞRULAMA:"):
            verification = stripped.split(":", 1)[1].strip()
            i += 1
            continue
        body.append(line)
        i += 1
    return body, sources, verification


def parse_answer(answer, trace=None, attachments=()):
    """Backend cevabı + trace -> AnswerView. UI KENDİ doğrulama kararını vermez."""
    text = str(answer or "").strip()
    lines = text.splitlines()
    body_lines, sources, verification = _split_sources(lines)
    outputs = []
    kept = []
    for line in body_lines:
        m = _OUTPUT_LINE.match(line)
        if m:
            candidate = m.group(1).strip().strip('"')
            outputs.append(candidate)
            if not os.path.exists(candidate):   # dosya yoksa satır gövdede kalsın (gizleme yok)
                kept.append(line)
        else:
            kept.append(line)
    for found in _ABS_FILE.findall("\n".join(kept)):
        if found not in outputs and found not in attachments and os.path.exists(found):
            outputs.append(found)
    outputs = [o for o in dict.fromkeys(outputs) if os.path.exists(o)]

    t = trace if isinstance(trace, dict) else (trace.to_dict() if hasattr(trace, "to_dict") else {})
    route = t.get("route") or ""
    try:
        from desktop.adapter import _ROUTE_LABELS
        route_label = _ROUTE_LABELS.get(route, "")
    except Exception:
        route_label = ""
    research_used = bool(t.get("used_research"))
    if not verification and research_used and t.get("research_status"):
        status = _RESEARCH_STATUS_TR.get(t.get("research_status"), str(t.get("research_status")))
        verification = (f"Araştırma sonucu: {status}"
                        f" · resmî kanıt {t.get('official_evidence_count', 0)}/{t.get('evidence_count', 0)}")
    refusal = (t.get("decision") == "refuse") or route in ("not_found_offline", "office_missing")
    summary = {k: t.get(k) for k in ("route", "confidence", "used_model", "used_research", "research_status",
                                     "consensus_status", "official_evidence_count", "evidence_count",
                                     "refusal_reason", "elapsed_ms") if k in t}
    return AnswerView(body="\n".join(kept).strip(), sources=sources, verification=verification,
                      route_label=route_label, outputs=outputs, research_used=research_used,
                      is_refusal=refusal, trace_summary=summary)
