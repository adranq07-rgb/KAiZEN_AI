"""KAİZEN Desktop -- basit yerel sohbet geçmişi (YALNIZ sunum/oturum özelliği).

Kaizen'in Experience/Memory/Learning sistemleriyle KARIŞTIRILMAZ: ayrı bir JSON dosyası
(data/ui/kazen_conversations.json). Buraya yalnız ekranda görünen metin, ek dosya adı/yolu ve
kaynak etiketleri yazılır -- API anahtarı/secret ASLA yazılmaz (yazılacak böyle bir alan yok).
Yazma atomiktir (geçici dosya + replace); bozuk dosya sohbetleri silmez, .bak olarak saklanır."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

from desktop.kazen_core import DEFAULT_MODE

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "ui" / "kazen_conversations.json"
_TITLE_MAX = 48


def _now():
    return datetime.now().isoformat(timespec="seconds")


class ChatStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else DEFAULT_PATH
        self._lock = threading.Lock()
        self.conversations = self._load()

    # -- kalıcılık ----------------------------------------------------------------
    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data.get("conversations", []) if isinstance(data, dict) else []
            return [c for c in items if isinstance(c, dict) and c.get("id")]
        except FileNotFoundError:
            return []
        except Exception:
            try:  # bozuk dosya: silme, yedekle
                self.path.replace(self.path.with_suffix(".bak"))
            except Exception:
                pass
            return []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "conversations": self.conversations}, handle, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
            return True
        except Exception:
            return False

    # -- API -------------------------------------------------------------------------
    def new_conversation(self, mode=DEFAULT_MODE):
        conv = {"id": uuid.uuid4().hex[:12], "title": "Yeni sohbet", "mode": mode,
                "created": _now(), "updated": _now(), "messages": []}
        with self._lock:
            self.conversations.insert(0, conv)
            self._save()
        return conv

    def get(self, conv_id):
        return next((c for c in self.conversations if c["id"] == conv_id), None)

    def add_message(self, conv_id, role, text, **extra):
        with self._lock:
            conv = self.get(conv_id)
            if conv is None:
                return None
            msg = {"role": role, "text": text, "time": _now()}
            msg.update({k: v for k, v in extra.items() if v})
            conv["messages"].append(msg)
            conv["updated"] = _now()
            if role == "user" and conv["title"] == "Yeni sohbet" and text.strip():
                first = " ".join(text.split())
                conv["title"] = first if len(first) <= _TITLE_MAX else first[:_TITLE_MAX - 1] + "…"
            self.conversations.sort(key=lambda c: c.get("updated", ""), reverse=True)
            self._save()
            return msg

    def rename(self, conv_id, title):
        with self._lock:
            conv = self.get(conv_id)
            if conv and title.strip():
                conv["title"] = title.strip()[:80]
                self._save()

    def delete(self, conv_id):
        with self._lock:
            self.conversations = [c for c in self.conversations if c["id"] != conv_id]
            self._save()

    def listing(self):
        return [(c["id"], c["title"], c.get("updated", "")) for c in self.conversations]

    def attachments_of(self, conv_id):
        conv = self.get(conv_id) or {}
        paths = []
        for m in conv.get("messages", []):
            paths.extend(a["path"] for a in m.get("attachments", []) if isinstance(a, dict) and a.get("path"))
        return paths

    def all_files(self):
        """Dosyalar sekmesi: tüm sohbetlerdeki ekler ve çıktılar."""
        files = []
        for c in self.conversations:
            for m in c.get("messages", []):
                for a in m.get("attachments", []):
                    files.append({"kind": "ek", "path": a.get("path", ""), "name": a.get("name", ""), "conv": c["title"],
                                  "time": m.get("time", "")})
                for o in m.get("outputs", []):
                    files.append({"kind": "çıktı", "path": o, "name": Path(o).name, "conv": c["title"],
                                  "time": m.get("time", "")})
        return files
