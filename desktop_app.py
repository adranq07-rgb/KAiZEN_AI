"""Kaizen AI - masaüstü sohbet uygulaması (Kaizen Desktop Alpha).

Amaç: Mali müşavirin (kullanıcının) Kaizen'i PowerShell/komut satırı olmadan, sıradan bir
masaüstü penceresinden -- masaüstündeki Kaizen simgesine çift tıklayarak -- kullanabilmesi.
`core.engine.KaizenEngine`'i doğrudan sarmalar -- karar mantığına hiç dokunmaz, yalnızca bir
arayüz katmanıdır (H1). Tüm biçimlendirme/durum/hata iş mantığı `desktop/adapter.py`'ye
ayrıştırılmıştır (bkz. o modülün docstring'i, Faz L) -- bu dosya yalnızca tkinter widget'larını
kurar ve adapter'ı çağırır.

Bağımlılık: yalnızca Python standart kütüphanesi (tkinter) + proje kökündeki `desktop/` paketi.
AGENTS.md ilkesi gereği yeni bir dış paket eklenmedi (bkz. desktop/ARCHITECTURE_DECISION.md).

Çalıştırma: `.venv\\Scripts\\python.exe desktop_app.py` ya da masaüstündeki "Kaizen" kısayoluna
(ya da `Kaizen_Baslat.bat` dosyasına) çift tıklayarak.
"""
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext, ttk

from core.engine import KaizenEngine
from desktop.adapter import (
    StatusMapper, context_panel_summary, full_inspector_lines, ErrorPresenter,
    ConversationHistory, STATE_STARTING, STATE_READY, STATE_BUSY, STATE_ENGINE_ERROR,
    STATE_ANSWER_ERROR,
)

BG = "#1e1e2e"
PANEL = "#282840"
SIDEBAR = "#20202f"
USER_COLOR = "#8ab4f8"
KAIZEN_COLOR = "#a6e3a1"
SYSTEM_COLOR = "#f9c74f"
ERROR_COLOR = "#f38ba8"
TEXT_COLOR = "#e8e8f0"
MUTED_COLOR = "#8888a0"
FONT = ("Segoe UI", 11)
FONT_BOLD = ("Segoe UI", 11, "bold")
FONT_SMALL = ("Segoe UI", 9)

_ICON_DIR = Path(__file__).resolve().parent / "desktop" / "icon"
_ICON_ICO = _ICON_DIR / "kaizen.ico"
_ICON_PNG = _ICON_DIR / "kaizen_256.png"

# F1 (madde 18, birebir): sol kenar çubuğu bölümleri. Her giriş (etiket, komut_metni)
# çiftidir -- komut_metni, `core/commands.py::CommandHandler`in ZATEN desteklediği bir
# metin komutudur (H1: iş mantığı burada YENİDEN YAZILMAZ, var olan komutlar YENİDEN
# KULLANILIR). None ise bu bölüm Alpha'da yalnızca bilgilendirici bir yer tutucudur.
_SIDEBAR_SECTIONS = [
    ("Yeni Sohbet", None),
    ("Sohbetler", None),
    ("Araştırma", "güncelle"),
    ("Bilgi Merkezi", "parametreler"),
    ("Öğrenilenler", "öğrendiklerim"),
    ("Kaynaklar", "kaynaklar"),
    ("Sistem", "durum"),
    ("Ayarlar", None),
]


class BrainInspectorWindow:
    """F2: Geliştirici / Brain Inspector paneli. Normal kullanıcı akışından TAMAMEN AYRI
    bir pencere (Toplevel) -- yalnız 'Sistem > Geliştirici Modu' ile açılır, varsayılan
    kapalıdır."""

    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("Kaizen — Brain Inspector (Geliştirici)")
        self.window.geometry("520x480")
        self.window.configure(bg=BG)
        tk.Label(
            self.window, text="Brain Inspector — son cevabın tam izleme kaydı (KaizenTrace)",
            bg=BG, fg=TEXT_COLOR, font=FONT_BOLD, pady=8,
        ).pack(fill="x", padx=10)
        self.text = scrolledtext.ScrolledText(
            self.window, wrap="word", bg=PANEL, fg=TEXT_COLOR, font=("Consolas", 10),
            state="disabled", borderwidth=0, highlightthickness=0, padx=10, pady=10,
        )
        self.text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def show_trace(self, trace):
        lines = full_inspector_lines(trace)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "\n".join(lines))
        self.text.configure(state="disabled")

    def destroyed(self):
        try:
            return not self.window.winfo_exists()
        except tk.TclError:
            return True


class KaizenDesktopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Kaizen AI")
        self.root.geometry("1180x700")
        self.root.configure(bg=BG)
        self.root.minsize(760, 480)
        self._set_window_icon()

        self.engine = None
        self.busy = False
        self.last_trace = None
        self.history = ConversationHistory()
        self.inspector = None  # BrainInspectorWindow ya da None (kapalı)
        self._ui_queue = queue.Queue()

        self._build_ui()
        self._poll_queue()

        self._set_status(STATE_STARTING)
        self._append("sistem", "Kaizen başlatılıyor, lütfen bekleyin...")
        threading.Thread(target=self._start_engine, daemon=True).start()

    # --- pencere simgesi (G: marka/ikon) ---------------------------------------------
    def _set_window_icon(self):
        try:
            if _ICON_ICO.exists():
                self.root.iconbitmap(default=str(_ICON_ICO))
        except tk.TclError:
            pass  # .ico Windows'a özgüdür; başka platformda sessizce atlanır
        try:
            if _ICON_PNG.exists():
                icon_img = tk.PhotoImage(file=str(_ICON_PNG))
                self.root.iconphoto(True, icon_img)
                self._icon_ref = icon_img  # GC'nin görüntüyü toplamaması için referans tut
        except tk.TclError:
            pass

    # --- arayüz kurulumu -----------------------------------------------------------
    def _build_ui(self):
        # --- sol kenar çubuğu (F1) ---
        sidebar = tk.Frame(self.root, bg=SIDEBAR, width=170)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(
            sidebar, text="KAIZEN", bg=SIDEBAR, fg=KAIZEN_COLOR,
            font=("Segoe UI", 15, "bold"), pady=16,
        ).pack(fill="x")
        for label, command_text in _SIDEBAR_SECTIONS:
            btn = tk.Button(
                sidebar, text=label, bg=SIDEBAR, fg=TEXT_COLOR, font=FONT,
                activebackground=PANEL, activeforeground=TEXT_COLOR, relief="flat",
                anchor="w", padx=16, pady=8, cursor="hand2", borderwidth=0,
                command=lambda l=label, c=command_text: self._on_sidebar_click(l, c),
            )
            btn.pack(fill="x")

        # --- sağ bağlam paneli (F1: Kaynaklar/Doğrulama/Güven durumu/principle) ---
        self.context_panel = tk.Frame(self.root, bg=PANEL, width=260)
        self.context_panel.pack(side="right", fill="y")
        self.context_panel.pack_propagate(False)
        tk.Label(
            self.context_panel, text="Bağlam", bg=PANEL, fg=TEXT_COLOR,
            font=FONT_BOLD, pady=10,
        ).pack(fill="x", padx=12)
        self.context_text = tk.Label(
            self.context_panel, text="Henüz bir cevap üretilmedi.", bg=PANEL, fg=MUTED_COLOR,
            font=FONT_SMALL, justify="left", anchor="nw", wraplength=230, padx=12,
        )
        self.context_text.pack(fill="both", expand=True, anchor="n")

        # --- orta alan (başlık + sohbet + yazı kutusu) ---
        center = tk.Frame(self.root, bg=BG)
        center.pack(side="left", fill="both", expand=True)

        header = tk.Frame(center, bg=PANEL, height=48)
        header.pack(side="top", fill="x")
        tk.Label(
            header, text="Kaizen AI — mali müşavir asistanı", bg=PANEL, fg=TEXT_COLOR,
            font=("Segoe UI", 13, "bold"), pady=10,
        ).pack(side="left", padx=14)
        self.status_label = tk.Label(
            header, text=StatusMapper.label_for_state(STATE_STARTING), bg=PANEL,
            fg=SYSTEM_COLOR, font=FONT,
        )
        self.status_label.pack(side="right", padx=14)

        self.chat = scrolledtext.ScrolledText(
            center, wrap="word", bg=BG, fg=TEXT_COLOR, font=FONT, state="disabled",
            borderwidth=0, highlightthickness=0, padx=12, pady=10,
        )
        self.chat.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 0))
        self.chat.tag_config("user", foreground=USER_COLOR, font=FONT_BOLD, spacing3=4)
        self.chat.tag_config("kaizen", foreground=KAIZEN_COLOR, font=FONT_BOLD, spacing3=4)
        self.chat.tag_config("sistem", foreground=SYSTEM_COLOR, font=("Segoe UI", 10, "italic"))
        self.chat.tag_config("hata", foreground=ERROR_COLOR, font=("Segoe UI", 10, "italic"))
        self.chat.tag_config("body", foreground=TEXT_COLOR, font=FONT, spacing3=10)
        self.chat.tag_config("meta", foreground=MUTED_COLOR, font=("Segoe UI", 9))

        bottom = tk.Frame(center, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=8, pady=8)

        self.entry = tk.Text(bottom, height=3, bg=PANEL, fg=TEXT_COLOR, font=FONT,
                              insertbackground=TEXT_COLOR, borderwidth=0, highlightthickness=1,
                              highlightbackground="#3a3a55", highlightcolor="#5a5aff", padx=8, pady=8)
        self.entry.pack(side="left", fill="both", expand=True)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Shift-Return>", lambda e: None)  # Shift+Enter: yeni satır
        self.entry.focus_set()

        self.send_btn = tk.Button(
            bottom, text="Gönder", command=self._on_send, bg="#5a5aff", fg="white",
            font=FONT_BOLD, activebackground="#7a7aff", relief="flat", padx=18, cursor="hand2",
        )
        self.send_btn.pack(side="right", fill="y", padx=(8, 0))

        help_bar = tk.Frame(center, bg=BG)
        help_bar.pack(side="bottom", fill="x", padx=12)
        tk.Label(
            help_bar, bg=BG, fg=MUTED_COLOR, font=FONT_SMALL,
            text="Enter: gönder · Shift+Enter: yeni satır · 'yardım' yaz ya da soldaki menüyü kullan",
        ).pack(side="left", pady=(0, 6))

    # --- sol menü aksiyonları ----------------------------------------------------------
    def _on_sidebar_click(self, label, command_text):
        if label == "Yeni Sohbet":
            self._new_chat()
            return
        if label == "Sohbetler":
            self._append("sistem", "Çoklu sohbet geçmişi Alpha sürümünde henüz yok; bu pencere "
                                    "tek bir oturumu gösterir.")
            return
        if label == "Ayarlar":
            self._show_settings()
            return
        if label == "Sistem":
            self._toggle_inspector()
        if command_text:
            self._send_text(command_text)

    def _new_chat(self):
        """H4: yalnız GUI'nin oturum-içi dökümünü temizler -- Kaizen'in gerçek hafızasına
        (learning_store/site_store/facts/cards) HİÇ dokunmaz, `self.engine` AYNI kalır."""
        self.history.clear()
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self._append("sistem", "Yeni sohbet başlatıldı (Kaizen'in hafızası korunuyor).")

    def _show_settings(self):
        flag = "kapalı (varsayılan)"
        if self.engine is not None:
            flag = "açık" if self.engine.config.learning_brain_enabled() else "kapalı (varsayılan)"
        self._append(
            "sistem",
            "Ayarlar (salt okunur, Alpha): Learning Brain = " + flag + ". "
            "Değiştirmek için config/Kaizen.json dosyasındaki learning.learning_brain_enabled "
            "alanını düzenleyip Kaizen'i yeniden başlat.",
        )

    def _toggle_inspector(self):
        if self.inspector is not None and not self.inspector.destroyed():
            self.inspector.show_trace(self.last_trace)
            self.inspector.window.lift()
            return
        self.inspector = BrainInspectorWindow(self.root)
        self.inspector.show_trace(self.last_trace)

    # --- motor başlatma (arka plan thread'i) ----------------------------------------
    def _start_engine(self):
        try:
            engine = KaizenEngine()
        except Exception as exc:
            self._ui_queue.put(("engine_error", exc))
            return
        self._ui_queue.put(("engine_ready", engine))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self._ui_queue.get_nowait()
                if kind == "engine_ready":
                    self.engine = payload
                    provider = self.engine.provider_manager.provider
                    names = [type(p).__name__ for p in getattr(provider, "providers", [provider])]
                    self._set_status(STATE_READY)
                    self.status_label.config(text=f"Hazır — {' → '.join(names)}", fg=KAIZEN_COLOR)
                    self._append("sistem", "Kaizen hazır. Sorunu yaz, ya da soldaki menüyü kullan.")
                elif kind == "engine_error":
                    self._set_status(STATE_ENGINE_ERROR)
                    self._append("hata", ErrorPresenter.user_message(payload))
                    self._log_technical(payload)
                elif kind == "answer":
                    question, answer, trace = payload
                    self.last_trace = trace
                    self._append("kaizen", answer, trace=trace)
                    self._update_context_panel(trace)
                    if self.inspector is not None and not self.inspector.destroyed():
                        self.inspector.show_trace(trace)
                    self._set_busy(False)
                    summary = StatusMapper.summarize_trace(trace)
                    if summary:
                        self.status_label.config(text=summary, fg=KAIZEN_COLOR)
                elif kind == "error":
                    self._append("hata", ErrorPresenter.user_message(payload))
                    self._log_technical(payload)
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _log_technical(self, exc):
        """H3: ham hata metni kullanıcıya DEĞİL, yalnız log dosyasına/motor logger'ına yazılır."""
        detail = ErrorPresenter.technical_detail(exc)
        if self.engine is not None:
            try:
                self.engine.logger.error(f"[Desktop] {detail}")
                return
            except Exception:
                pass
        print(f"[Kaizen Desktop] {detail}", file=sys.stderr)

    # --- mesaj gönderme --------------------------------------------------------------
    def _on_enter(self, event):
        if event.state & 0x0001:  # Shift basılıysa yeni satıra izin ver
            return None
        self._on_send()
        return "break"

    def _on_send(self):
        if self.busy:
            return
        text = self.entry.get("1.0", "end").strip()
        if not text:
            return
        if self.engine is None:
            self._append("sistem", "Kaizen henüz hazır değil, birkaç saniye bekle.")
            return
        self.entry.delete("1.0", "end")
        self._send_text(text)

    def _send_text(self, text):
        """Sol menüden gelen komutlar ve kullanıcının yazdığı metin AYNI yoldan (motorun
        GERÇEK `cevap_ver()`'i) geçer -- iki AYRI kod yolu YOKTUR."""
        if self.engine is None:
            self._append("sistem", "Kaizen henüz hazır değil, birkaç saniye bekle.")
            return
        if self.busy:
            return
        self._append("user", text)
        self._set_busy(True)
        threading.Thread(target=self._ask_engine, args=(text,), daemon=True).start()

    def _ask_engine(self, question):
        try:
            answer = self.engine.cevap_ver(question)
        except Exception as exc:
            self._ui_queue.put(("error", exc))
            return
        trace = getattr(self.engine.brain, "last_trace", None)
        self._ui_queue.put(("answer", (question, answer, trace)))

    def _set_busy(self, value):
        self.busy = value
        self.send_btn.config(state="disabled" if value else "normal")
        if value:
            self._set_status(STATE_BUSY)
            self.status_label.config(text=StatusMapper.label_for_state(STATE_BUSY), fg=SYSTEM_COLOR)
            self._append("sistem", "Kaizen düşünüyor...")

    def _set_status(self, state):
        self._current_state = state

    # --- bağlam paneli (F1) -----------------------------------------------------------
    def _update_context_panel(self, trace):
        summary = context_panel_summary(trace)
        if summary is None:
            self.context_text.config(text="Henüz bir cevap üretilmedi.")
            return
        lines = [
            f"Güven durumu: {summary.confidence_label}",
            f"Kaynak: {summary.route_label}",
        ]
        if summary.used_current_research:
            lines.append("Güncel araştırma kullanıldı.")
        if summary.principle_hint:
            name, confidence = summary.principle_hint
            lines.append(f"İlgili ilke (yardımcı): {name} ({confidence})")
        if summary.retrieval_score is not None:
            lines.append(f"Kanıt örtüşme skoru: {summary.retrieval_score}")
        self.context_text.config(text="\n\n".join(lines))

    # --- sohbet penceresine yazma ----------------------------------------------------
    def _append(self, who, text, trace=None):
        role = {"user": "user", "kaizen": "kaizen", "hata": "sistem"}.get(who, "sistem")
        self.history.add(role if who != "hata" else "sistem", text, trace=trace)
        self.chat.configure(state="normal")
        stamp = datetime.now().strftime("%H:%M")
        if who == "user":
            self.chat.insert("end", f"Sen  {stamp}\n", ("user",))
            self.chat.insert("end", f"{text}\n\n", ("body",))
        elif who == "kaizen":
            self.chat.insert("end", f"Kaizen  {stamp}\n", ("kaizen",))
            self.chat.insert("end", f"{text}\n\n", ("body",))
        elif who == "hata":
            self.chat.insert("end", f"— {text} —\n\n", ("hata",))
        else:
            self.chat.insert("end", f"— {text} —\n\n", ("sistem",))
        self.chat.configure(state="disabled")
        self.chat.see("end")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    root = tk.Tk()
    try:
        style = ttk.Style(root)
        style.theme_use("clam")
    except Exception:
        pass
    app = KaizenDesktopApp(root)
    try:
        root.mainloop()
    finally:
        if app.engine is not None:
            app.engine.shutdown()


if __name__ == "__main__":
    main()
