"""KAİZEN Desktop -- UI'dan bağımsız denetleyici (tkinter'sız).

Akış (ayrı cevap motoru YOK):
  Normal mesaj : UI -> KaizenEngine.cevap_ver() -> UI
  Dosyalı mesaj: UI -> dosya referansı (tırnaklı gerçek yol) -> mesaja eklenir -> KaizenEngine.cevap_ver()
                 -> Document Engine -> Accounting Brain -> final cevap -> UI
Uzun işlem arka plan iş parçacığında çalışır; UI yalnız `events` kuyruğunu okur (donmaz)."""
from __future__ import annotations

import queue
import threading
import time
import traceback

from desktop import kazen_core as core
from desktop.chat_store import ChatStore

STATUS_THINKING = "Kaizen düşünüyor..."
STATUS_RESEARCH = "Kaynaklar araştırılıyor..."
STATUS_DOCUMENT = "Belge analiz ediliyor..."


class KazenController:
    def __init__(self, engine_factory=None, store=None):
        self.engine_factory = engine_factory or self._default_factory
        self.store = store or ChatStore()
        self.events = queue.Queue()
        self.engine = None
        self.engine_error = None
        self.busy = False
        self.mode = core.DEFAULT_MODE
        self.current_id = None

    @staticmethod
    def _default_factory():
        from core.engine import KaizenEngine
        return KaizenEngine()

    # -- motor ----------------------------------------------------------------------
    def start_engine(self):
        threading.Thread(target=self._start_engine, daemon=True).start()

    def _start_engine(self):
        try:
            self.engine = self.engine_factory()
            self.events.put(("engine_ready", None))
        except Exception as exc:
            self.engine_error = f"{type(exc).__name__}: {exc}"
            self.events.put(("engine_error", self.engine_error))

    @property
    def config(self):
        return getattr(self.engine, "config", None)

    # -- sohbetler --------------------------------------------------------------------
    def set_mode(self, mode):
        if not core.mode_enabled(mode):
            return False
        self.mode = mode
        return True

    def new_conversation(self):
        conv = self.store.new_conversation(self.mode)
        self.current_id = conv["id"]
        return conv

    def open_conversation(self, conv_id):
        if self.store.get(conv_id):
            self.current_id = conv_id
            return self.store.get(conv_id)
        return None

    # -- mesaj gönderme -----------------------------------------------------------------
    def initial_status(self, message, has_attachment):
        if has_attachment:
            return STATUS_DOCUMENT
        try:
            if self.engine is not None and self.engine.brain.needs_current_research(message):
                return STATUS_RESEARCH
        except Exception:
            pass
        return STATUS_THINKING

    def submit(self, text, new_attachments=()):
        """UI iş parçacığından çağrılır; hemen döner. Sonuç `events` kuyruğuna düşer:
        ('user', msg) ('status', str) ('answer', (AnswerView, msg)) ('error', str) ('attach_error', [str])"""
        if self.busy:
            self.events.put(("error", "Önceki istek hâlâ çalışıyor."))
            return False
        if self.engine is None:
            self.events.put(("error", "Kaizen motoru henüz hazır değil." if not self.engine_error
                             else f"Kaizen motoru başlatılamadı: {self.engine_error}"))
            return False
        checks = [core.validate_attachment(p) for p in new_attachments]
        bad = [c.error for c in checks if not c.ok]
        if bad:
            self.events.put(("attach_error", bad))
            return False
        good = [c.path for c in checks]
        if not (text or "").strip() and not good:
            return False
        if self.current_id is None:
            self.new_conversation()
        conv_id = self.current_id
        previous = self.store.attachments_of(conv_id)
        message, used = core.compose_message(text, good, previous)
        attachments = [{"path": p, "name": p.replace("\\", "/").rsplit("/", 1)[-1]} for p in used]
        shown = (text or "").strip() or "Bu dosyayı oku"
        user_msg = self.store.add_message(conv_id, "user", shown, attachments=attachments if good else [])
        self.events.put(("user", user_msg))
        self.busy = True
        self.events.put(("status", self.initial_status(message, bool(used))))
        threading.Thread(target=self._run, args=(conv_id, message, used), daemon=True).start()
        return True

    def _run(self, conv_id, message, used):
        started = time.perf_counter()
        try:
            answer = self.engine.cevap_ver(message)
            trace = getattr(getattr(self.engine, "brain", None), "last_trace", None)
            view = core.parse_answer(answer, trace, attachments=used)
            meta = dict(view.trace_summary)
            meta["seconds"] = round(time.perf_counter() - started, 1)
            msg = self.store.add_message(
                conv_id, "kaizen", view.body, outputs=view.outputs,
                sources=[{"label": s.label, "url": s.url} for s in view.sources],
                verification=view.verification, route=view.route_label, refusal=view.is_refusal, meta=meta)
            self.events.put(("answer", (view, msg)))
        except Exception as exc:  # UI çökmesin
            self.events.put(("error", f"Cevap üretilemedi: {type(exc).__name__}: {exc}"))
        finally:
            self.busy = False
            self.events.put(("status", ""))
