"""KAİZEN Desktop -- tkinter görünüm katmanı (yalnız sunum; iş mantığı desktop/controller.py'de).

Düzen: sol kenar çubuğu (KAİZEN, + Yeni Sohbet, Muhasebe / Genel AI — Yakında, sohbet geçmişi,
Dosyalar, Ayarlar) + ana alan (sohbet | dosyalar | ayarlar) + alt giriş (Dosya Ekle, mesaj, Gönder).
Yeni bağımlılık YOK (yalnız stdlib tkinter). Backend'e yalnız KazenController üzerinden erişir."""
from __future__ import annotations

import time
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from desktop import kazen_core as core
from desktop.controller import KazenController
from desktop.health import BAD, OK, WARN, collect_health
from desktop.kazen_os import install_file_drop, open_path, reveal_in_folder
from desktop.markdown_view import parse_markdown, table_as_text

# --- Görsel kimlik: sade, kurumsal, açık tema -------------------------------------------------
NAVY = "#14233a"
NAVY_2 = "#1d3252"
NAVY_HOVER = "#2a4468"
SIDE_TEXT = "#dbe4f0"
SIDE_MUTED = "#8fa3bf"
BG = "#f5f7fa"
SURFACE = "#ffffff"
LINE = "#dde3ec"
TEXT = "#1b2430"
MUTED = "#667085"
ACCENT = "#1f5fa8"
ACCENT_DARK = "#174a85"
USER_BG = "#e8f0fb"
CHIP_BG = "#eaeef4"
OK_COLOR = "#1f8a4c"
WARN_COLOR = "#b7791f"
BAD_COLOR = "#c0392b"
CODE_BG = "#f1f4f8"

F = "Segoe UI"
FONT = (F, 10)
FONT_BOLD = (F, 10, "bold")
FONT_SMALL = (F, 9)
FONT_TITLE = (F, 16, "bold")
MONO = ("Consolas", 10)

STATE_COLORS = {OK: OK_COLOR, WARN: WARN_COLOR, BAD: BAD_COLOR}


class KazenApp:
    def __init__(self, root, controller=None):
        self.root = root
        self.ctl = controller or KazenController()
        self.pending = []                 # eklenmeyi bekleyen dosya yolları
        self._busy_since = None
        self._status_text = ""
        self._link_n = 0
        self._build_window()
        self._build_sidebar()
        self._build_main()
        self._refresh_history()
        self.show_view("chat")
        self.ctl.new_conversation()
        self._refresh_history()
        self._render_conversation()
        self.ctl.start_engine()
        self._set_status("Kaizen başlatılıyor...")
        self.dnd_ok = install_file_drop(self.root, self.on_files_dropped)
        if not self.dnd_ok:
            self._set_status("Sürükle-bırak kullanılamıyor; '+ Dosya Ekle' düğmesini kullanın.", transient=True)
        self.root.after(120, self._poll)
        self.root.after(500, self._tick)

    # ------------------------------------------------------------------ pencere ----------------
    def _build_window(self):
        self.root.title(core.APP_NAME)
        self.root.geometry("1180x760")
        self.root.minsize(920, 600)
        self.root.configure(bg=BG)
        icon = Path(__file__).resolve().parent / "icon" / "kaizen.ico"
        try:
            if icon.exists():
                self.root.iconbitmap(str(icon))
        except Exception:
            pass
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _side_button(self, parent, text, command, state="normal", bold=False):
        btn = tk.Button(parent, text=text, command=command, anchor="w", relief="flat", bd=0, padx=14, pady=8,
                        bg=NAVY, fg=SIDE_TEXT, activebackground=NAVY_HOVER, activeforeground="white",
                        disabledforeground=SIDE_MUTED, font=FONT_BOLD if bold else FONT, cursor="hand2", state=state)
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=NAVY_HOVER) if str(b["state"]) == "normal" else None)
        btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=NAVY))
        return btn

    def _build_sidebar(self):
        side = tk.Frame(self.root, bg=NAVY, width=260)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        side.rowconfigure(5, weight=1)
        tk.Label(side, text=core.APP_NAME, bg=NAVY, fg="white", font=(F, 20, "bold"), anchor="w",
                 padx=16).grid(row=0, column=0, sticky="ew", pady=(18, 2))
        tk.Label(side, text="Muhasebe asistanı", bg=NAVY, fg=SIDE_MUTED, font=FONT_SMALL, anchor="w",
                 padx=16).grid(row=1, column=0, sticky="ew", pady=(0, 12))
        new_btn = tk.Button(side, text="+  Yeni Sohbet", command=self.on_new_chat, relief="flat", bd=0, padx=14,
                            pady=9, bg=ACCENT, fg="white", activebackground=ACCENT_DARK, activeforeground="white",
                            font=FONT_BOLD, cursor="hand2")
        new_btn.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
        modes = tk.Frame(side, bg=NAVY)
        modes.grid(row=3, column=0, sticky="ew")
        self.mode_buttons = {}
        for key, info in core.MODES.items():
            state = "normal" if info["enabled"] else "disabled"
            btn = self._side_button(modes, info["label"], lambda k=key: self.on_mode(k), state=state,
                                    bold=(key == core.DEFAULT_MODE))
            btn.pack(fill="x")
            self.mode_buttons[key] = btn
        self.mode_buttons[core.DEFAULT_MODE].configure(bg=NAVY_2)
        tk.Label(side, text="SOHBETLER", bg=NAVY, fg=SIDE_MUTED, font=(F, 8, "bold"), anchor="w",
                 padx=16).grid(row=4, column=0, sticky="ew", pady=(14, 4))
        hist = tk.Frame(side, bg=NAVY)
        hist.grid(row=5, column=0, sticky="nsew")
        hist.rowconfigure(0, weight=1)
        hist.columnconfigure(0, weight=1)
        self.history = tk.Listbox(hist, bg=NAVY, fg=SIDE_TEXT, selectbackground=NAVY_HOVER, selectforeground="white",
                                  bd=0, highlightthickness=0, activestyle="none", font=FONT, cursor="hand2")
        self.history.grid(row=0, column=0, sticky="nsew", padx=(8, 0))
        self.history.bind("<<ListboxSelect>>", self.on_history_select)
        bottom = tk.Frame(side, bg=NAVY)
        bottom.grid(row=6, column=0, sticky="ew", pady=(6, 10))
        self._side_button(bottom, "📁  Dosyalar", lambda: self.show_view("files")).pack(fill="x")
        self._side_button(bottom, "⚙  Ayarlar", lambda: self.show_view("settings")).pack(fill="x")
        self._history_ids = []

    # ------------------------------------------------------------------ ana alan ---------------
    def _build_main(self):
        main = tk.Frame(self.root, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        self.views = {}
        self._build_chat_view(main)
        self._build_files_view(main)
        self._build_settings_view(main)

    def _build_chat_view(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)
        self.views["chat"] = frame
        header = tk.Frame(frame, bg=SURFACE, highlightbackground=LINE, highlightthickness=1)
        header.grid(row=0, column=0, sticky="ew")
        self.title_label = tk.Label(header, text="Yeni sohbet", bg=SURFACE, fg=TEXT, font=(F, 12, "bold"), anchor="w",
                                    padx=18, pady=10)
        self.title_label.pack(side="left")
        self.mode_label = tk.Label(header, text="Mod: Muhasebe", bg=SURFACE, fg=MUTED, font=FONT_SMALL, padx=18)
        self.mode_label.pack(side="right")

        body = tk.Frame(frame, bg=BG)
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.chat = tk.Text(body, wrap="word", bg=BG, fg=TEXT, font=FONT, bd=0, highlightthickness=0, padx=28,
                            pady=14, spacing1=2, spacing3=2, cursor="arrow", state="disabled")
        scroll = ttk.Scrollbar(body, command=self.chat.yview)
        self.chat.configure(yscrollcommand=scroll.set)
        self.chat.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self._configure_chat_tags()

        bottom = tk.Frame(frame, bg=BG)
        bottom.grid(row=2, column=0, sticky="ew", padx=24, pady=(4, 14))
        bottom.columnconfigure(0, weight=1)
        self.status_label = tk.Label(bottom, text="", bg=BG, fg=ACCENT, font=FONT_SMALL, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.chips = tk.Frame(bottom, bg=BG)
        self.chips.grid(row=1, column=0, sticky="ew")
        box = tk.Frame(bottom, bg=SURFACE, highlightbackground=LINE, highlightthickness=1)
        box.grid(row=2, column=0, sticky="ew")
        box.columnconfigure(1, weight=1)
        attach = tk.Button(box, text="+ Dosya Ekle", command=self.on_add_files, relief="flat", bd=0, padx=12, pady=8,
                           bg=SURFACE, fg=ACCENT, activebackground=CHIP_BG, font=FONT_BOLD, cursor="hand2")
        attach.grid(row=0, column=0, sticky="s", padx=(4, 0), pady=4)
        self.input = tk.Text(box, height=3, wrap="word", font=(F, 11), bd=0, highlightthickness=0, bg=SURFACE, fg=TEXT,
                             padx=8, pady=8, insertbackground=TEXT)
        self.input.grid(row=0, column=1, sticky="ew")
        self.input.bind("<Return>", self.on_enter)
        self.input.bind("<Shift-Return>", lambda e: None)
        self.send_btn = tk.Button(box, text="Gönder", command=self.on_send, relief="flat", bd=0, padx=18, pady=8,
                                  bg=ACCENT, fg="white", activebackground=ACCENT_DARK, activeforeground="white",
                                  font=FONT_BOLD, cursor="hand2")
        self.send_btn.grid(row=0, column=2, sticky="s", padx=8, pady=8)
        tk.Label(bottom, text="Enter: gönder · Shift+Enter: yeni satır · Dosyaları pencereye sürükleyip bırakabilirsiniz",
                 bg=BG, fg=MUTED, font=(F, 8), anchor="w").grid(row=3, column=0, sticky="ew", pady=(4, 0))

    def _configure_chat_tags(self):
        c = self.chat
        c.tag_configure("who_user", foreground=ACCENT, font=(F, 9, "bold"), spacing1=14)
        c.tag_configure("who_kaizen", foreground=NAVY, font=(F, 9, "bold"), spacing1=14)
        c.tag_configure("time", foreground=MUTED, font=(F, 8))
        c.tag_configure("user_body", background=USER_BG, lmargin1=10, lmargin2=10, rmargin=10, spacing1=4, spacing3=4)
        c.tag_configure("kaizen_body", lmargin1=2, lmargin2=2)
        c.tag_configure("bold", font=FONT_BOLD)
        c.tag_configure("code", font=MONO, background=CODE_BG)
        c.tag_configure("h1", font=(F, 15, "bold"), spacing1=10, foreground=NAVY)
        c.tag_configure("h2", font=(F, 13, "bold"), spacing1=8, foreground=NAVY)
        c.tag_configure("h3", font=(F, 11, "bold"), spacing1=6, foreground=NAVY)
        c.tag_configure("section", foreground=NAVY, spacing1=6)
        c.tag_configure("bullet", lmargin1=16, lmargin2=32)
        c.tag_configure("numbered", lmargin1=16, lmargin2=36)
        c.tag_configure("table", font=MONO, background=CODE_BG, lmargin1=8, lmargin2=8, spacing1=2, spacing3=2)
        c.tag_configure("codeblock", font=MONO, background=CODE_BG, lmargin1=8, lmargin2=8)
        c.tag_configure("rule", foreground=LINE)
        c.tag_configure("chip", background=CHIP_BG, foreground=TEXT, font=FONT_BOLD, lmargin1=10, lmargin2=10)
        c.tag_configure("err", foreground=BAD_COLOR, font=FONT_BOLD)
        c.tag_configure("sys", foreground=MUTED, font=(F, 9, "italic"))
        c.tag_configure("src_head", foreground=NAVY, font=(F, 9, "bold"), spacing1=10)
        c.tag_configure("src", foreground=TEXT, font=FONT_SMALL, lmargin1=10, lmargin2=24)
        c.tag_configure("verify", foreground=OK_COLOR, font=(F, 9, "bold"), lmargin1=10, lmargin2=24)
        c.tag_configure("refuse", foreground=WARN_COLOR, font=FONT_SMALL)
        c.tag_configure("link", foreground=ACCENT, underline=True)

    def _build_files_view(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)
        self.views["files"] = frame
        tk.Label(frame, text="Dosyalar", bg=BG, fg=TEXT, font=FONT_TITLE, anchor="w", padx=24, pady=16).grid(
            row=0, column=0, sticky="ew")
        cols = ("tur", "ad", "sohbet", "zaman")
        self.files_tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for col, title, width in (("tur", "Tür", 70), ("ad", "Dosya", 360), ("sohbet", "Sohbet", 260), ("zaman", "Zaman", 150)):
            self.files_tree.heading(col, text=title)
            self.files_tree.column(col, width=width, anchor="w")
        self.files_tree.grid(row=1, column=0, sticky="nsew", padx=24)
        buttons = tk.Frame(frame, bg=BG)
        buttons.grid(row=2, column=0, sticky="ew", padx=24, pady=12)
        for text, cmd in (("Aç", self.on_file_open), ("Klasörde Göster", self.on_file_reveal), ("Yenile", self._refresh_files)):
            tk.Button(buttons, text=text, command=cmd, relief="flat", bd=0, padx=14, pady=7, bg=ACCENT, fg="white",
                      activebackground=ACCENT_DARK, activeforeground="white", font=FONT_BOLD,
                      cursor="hand2").pack(side="left", padx=(0, 8))
        self._file_rows = {}

    def _build_settings_view(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        self.views["settings"] = frame
        tk.Label(frame, text="Ayarlar", bg=BG, fg=TEXT, font=FONT_TITLE, anchor="w", padx=24, pady=16).grid(
            row=0, column=0, sticky="ew")
        tk.Label(frame, text="Backend durumu", bg=BG, fg=NAVY, font=(F, 11, "bold"), anchor="w", padx=24).grid(
            row=1, column=0, sticky="ew")
        self.health_box = tk.Frame(frame, bg=SURFACE, highlightbackground=LINE, highlightthickness=1)
        self.health_box.grid(row=2, column=0, sticky="ew", padx=24, pady=8)
        self.health_box.columnconfigure(1, weight=1)
        self.health_btn = tk.Button(frame, text="Durumu Yenile", command=self.refresh_health, relief="flat", bd=0,
                                    padx=14, pady=7, bg=ACCENT, fg="white", activebackground=ACCENT_DARK,
                                    activeforeground="white", font=FONT_BOLD, cursor="hand2")
        self.health_btn.grid(row=3, column=0, sticky="w", padx=24, pady=4)
        tk.Label(frame, text="API anahtarları bu ekranda gösterilmez; yalnızca ortam değişkeninden okunur.",
                 bg=BG, fg=MUTED, font=FONT_SMALL, anchor="w", padx=24).grid(row=4, column=0, sticky="ew", pady=(8, 0))

    # ------------------------------------------------------------------ görünüm geçişi ---------
    def show_view(self, name):
        for key, frame in self.views.items():
            frame.grid() if key == name else frame.grid_remove()
        if name == "files":
            self._refresh_files()
        elif name == "settings":
            self.refresh_health()

    # ------------------------------------------------------------------ sohbet işlemleri -------
    def on_mode(self, mode):
        if self.ctl.set_mode(mode):
            self.mode_label.configure(text="Mod: " + core.MODES[mode]["label"])

    def on_new_chat(self):
        if self.ctl.busy:
            self._set_status("Önceki istek tamamlanana kadar bekleyin.", transient=True)
            return
        self.ctl.new_conversation()
        self.pending.clear()
        self._refresh_chips()
        self._refresh_history()
        self._render_conversation()
        self.show_view("chat")
        self.input.focus_set()

    def on_history_select(self, _event):
        sel = self.history.curselection()
        if not sel or self.ctl.busy:
            return
        conv = self.ctl.open_conversation(self._history_ids[sel[0]])
        if conv:
            self.pending.clear()
            self._refresh_chips()
            self._render_conversation()
            self.show_view("chat")

    def _refresh_history(self):
        self.history.delete(0, "end")
        self._history_ids = []
        for conv_id, title, _updated in self.ctl.store.listing():
            self.history.insert("end", "  " + title)
            self._history_ids.append(conv_id)
            if conv_id == self.ctl.current_id:
                self.history.selection_set("end")

    def on_enter(self, event):
        if event.state & 0x0001:     # Shift
            return None
        self.on_send()
        return "break"

    def on_send(self):
        text = self.input.get("1.0", "end").strip()
        if not text and not self.pending:
            return
        if self.ctl.submit(text, list(self.pending)):
            self.input.delete("1.0", "end")
            self.pending.clear()
            self._refresh_chips()

    # ------------------------------------------------------------------ dosya ekleme -----------
    def on_add_files(self):
        patterns = " ".join("*" + s for s in core.SUPPORTED_READ_SUFFIXES)
        paths = filedialog.askopenfilenames(
            title="Dosya Ekle", filetypes=[("Desteklenen dosyalar", patterns), ("Tüm dosyalar", "*.*")])
        if paths:
            self.add_files(list(paths))

    def on_files_dropped(self, paths):
        self.show_view("chat")
        self.add_files(paths)

    def add_files(self, paths):
        errors = []
        for path in paths:
            check = core.validate_attachment(path)
            if check.ok:
                if check.path not in self.pending:
                    self.pending.append(check.path)
            else:
                errors.append(check.error)
        self._refresh_chips()
        if errors:   # sessizce yok sayılmaz
            self._append_system("\n".join("⚠ " + e for e in errors), error=True)
            messagebox.showwarning(core.APP_NAME, "\n".join(errors))
        self.input.focus_set()

    def _refresh_chips(self):
        for child in self.chips.winfo_children():
            child.destroy()
        for path in self.pending:
            chip = tk.Frame(self.chips, bg=CHIP_BG)
            chip.pack(side="left", padx=(0, 6), pady=(0, 6))
            tk.Label(chip, text=f"📎 {Path(path).name}", bg=CHIP_BG, fg=TEXT, font=FONT_SMALL, padx=8, pady=3).pack(side="left")
            tk.Button(chip, text="✕", command=lambda p=path: self._remove_pending(p), relief="flat", bd=0, bg=CHIP_BG,
                      fg=MUTED, activebackground=LINE, cursor="hand2", font=FONT_SMALL).pack(side="left")

    def _remove_pending(self, path):
        if path in self.pending:
            self.pending.remove(path)
        self._refresh_chips()

    # ------------------------------------------------------------------ olay döngüsü ----------
    def _poll(self):
        try:
            while True:
                kind, payload = self.ctl.events.get_nowait()
                if kind == "engine_ready":
                    self._set_status("Kaizen hazır.", transient=True)
                elif kind == "engine_error":
                    self._append_system(f"Kaizen motoru başlatılamadı: {payload}", error=True)
                    self._set_status("")
                elif kind == "user":
                    self._append_user(payload)
                elif kind == "status":
                    self._set_busy(bool(payload), payload)
                elif kind == "answer":
                    view, msg = payload
                    self._append_kaizen(msg)
                    self._refresh_history()
                    self.title_label.configure(text=(self.ctl.store.get(self.ctl.current_id) or {}).get("title", ""))
                elif kind == "error":
                    self._append_system(str(payload), error=True)
                elif kind == "attach_error":
                    self._append_system("\n".join("⚠ " + e for e in payload), error=True)
        except Exception as exc:
            if type(exc).__name__ != "Empty":
                self._append_system(f"Arayüz hatası: {type(exc).__name__}", error=True)
        self.root.after(120, self._poll)

    def _set_busy(self, busy, text):
        self._busy_since = time.monotonic() if busy else None
        self._status_text = text if busy else ""
        self.send_btn.configure(state="disabled" if busy else "normal")
        self.status_label.configure(text=(self._status_text.rstrip(".") + ".   (0 sn)") if busy else "")

    def _set_status(self, text, transient=False):
        self.status_label.configure(text=text)
        if transient:
            self.root.after(4000, lambda: self.status_label.configure(text="") if not self._busy_since else None)

    def _tick(self):
        if self._busy_since is not None:
            elapsed = int(time.monotonic() - self._busy_since)
            dots = "." * (elapsed % 3 + 1)
            self.status_label.configure(text=f"{self._status_text.rstrip('.')}{dots}   ({elapsed} sn)")
        self.root.after(500, self._tick)

    # ------------------------------------------------------------------ sohbet çizimi -----------
    def _render_conversation(self):
        conv = self.ctl.store.get(self.ctl.current_id) or {"title": "Yeni sohbet", "messages": []}
        self.title_label.configure(text=conv["title"])
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        if not conv["messages"]:
            self._append_system("Merhaba, ben KAİZEN. Muhasebe sorunuzu yazın ya da bir fatura / Excel / PDF ekleyin.")
        for msg in conv["messages"]:
            if msg["role"] == "user":
                self._append_user(msg)
            else:
                self._append_kaizen(msg)

    def _write(self, text, *tags):
        self.chat.configure(state="normal")
        self.chat.insert("end", text, tags)
        self.chat.configure(state="disabled")

    def _stamp(self, msg):
        try:
            return datetime.fromisoformat(msg.get("time", "")).strftime("%H:%M")
        except Exception:
            return ""

    def _append_user(self, msg):
        self._write("\nSiz  ", "who_user")
        self._write(self._stamp(msg) + "\n", "time")
        for att in msg.get("attachments", []):
            self._write(f"📎 {att.get('name', '')}\n", "chip")
        self._write(msg.get("text", "") + "\n", "user_body")
        self.chat.see("end")

    def _append_system(self, text, error=False):
        self._write("\n" + text + "\n", "err" if error else "sys")
        self.chat.see("end")

    def _insert_inline(self, spans, *base):
        for text, style in spans:
            self._write(text, *base, *( (style,) if style else () ))

    def _render_markdown(self, text):
        for block in parse_markdown(text):
            kind = block.kind
            if kind == "blank":
                self._write("\n", "kaizen_body")
            elif kind == "heading":
                self._insert_inline(block.spans, "h%d" % min(block.level, 3))
                self._write("\n", "kaizen_body")
            elif kind == "section":
                self._insert_inline(block.spans, "section")
                self._write("\n", "kaizen_body")
            elif kind == "bullet":
                self._write("•  ", "bullet")
                self._insert_inline(block.spans, "bullet")
                self._write("\n", "bullet")
            elif kind == "numbered":
                self._write(block.marker + "  ", "numbered")
                self._insert_inline(block.spans, "numbered")
                self._write("\n", "numbered")
            elif kind == "table":
                self._write(table_as_text(block.rows) + "\n", "table")
            elif kind == "code":
                self._write(block.text + "\n", "codeblock")
            elif kind == "rule":
                self._write("─" * 48 + "\n", "rule")
            else:
                self._insert_inline(block.spans, "kaizen_body")
                self._write("\n", "kaizen_body")

    def _link(self, text, url):
        self._link_n += 1
        tag = f"lnk{self._link_n}"
        self.chat.tag_configure(tag, foreground=ACCENT, underline=True)
        self.chat.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
        self.chat.tag_bind(tag, "<Enter>", lambda e: self.chat.configure(cursor="hand2"))
        self.chat.tag_bind(tag, "<Leave>", lambda e: self.chat.configure(cursor="arrow"))
        self._write(text, "src", tag)

    def _append_kaizen(self, msg):
        self._write("\nKAİZEN  ", "who_kaizen")
        route = msg.get("route") or ""
        self._write(self._stamp(msg) + (f" · {route}" if route else "") + "\n", "time")
        self._render_markdown(msg.get("text", ""))
        sources = msg.get("sources") or []
        verification = msg.get("verification") or ""
        if sources or verification:
            self._write("Kaynaklar\n", "src_head")
            for src in sources:
                self._write("✓ ", "src")
                if src.get("url"):
                    self._link(src.get("label", src["url"]), src["url"])
                else:
                    self._write(src.get("label", ""), "src")
                self._write("\n", "src")
            if verification:
                self._write("✓ " + verification + "\n", "verify")
        for path in msg.get("outputs") or []:
            self._write(f"\n{core.file_icon(path)} {Path(path).name}   ", "chip")
            for label, fn in (("Aç", lambda p=path: self._open(p)), ("Klasörde Göster", lambda p=path: self._reveal(p))):
                btn = tk.Button(self.chat, text=label, command=fn, relief="flat", bd=0, padx=8, pady=1, bg=ACCENT,
                                fg="white", activebackground=ACCENT_DARK, activeforeground="white", font=FONT_SMALL,
                                cursor="hand2")
                self.chat.configure(state="normal")
                self.chat.window_create("end", window=btn, padx=3)
                self.chat.configure(state="disabled")
            self._write("\n", "kaizen_body")
        self.chat.see("end")

    # ------------------------------------------------------------------ dosyalar / ayarlar ------
    def _open(self, path):
        ok, err = open_path(path)
        if not ok:
            messagebox.showwarning(core.APP_NAME, err)

    def _reveal(self, path):
        ok, err = reveal_in_folder(path)
        if not ok:
            messagebox.showwarning(core.APP_NAME, err)

    def _refresh_files(self):
        self.files_tree.delete(*self.files_tree.get_children())
        self._file_rows = {}
        for item in reversed(self.ctl.store.all_files()):
            iid = self.files_tree.insert("", "end", values=(item["kind"], item["name"], item["conv"],
                                                            item["time"].replace("T", " ")))
            self._file_rows[iid] = item["path"]

    def _selected_file(self):
        sel = self.files_tree.selection()
        return self._file_rows.get(sel[0]) if sel else None

    def on_file_open(self):
        path = self._selected_file()
        if path:
            self._open(path)

    def on_file_reveal(self):
        path = self._selected_file()
        if path:
            self._reveal(path)

    def refresh_health(self):
        import threading
        self.health_btn.configure(state="disabled", text="Kontrol ediliyor...")

        def work():
            config = self.ctl.config
            if config is None:
                from config.config_manager import ConfigManager
                config = ConfigManager()
            items = collect_health(config, engine_ready=self.ctl.engine is not None)
            self.root.after(0, lambda: self._show_health(items))

        threading.Thread(target=work, daemon=True).start()

    def _show_health(self, items):
        for child in self.health_box.winfo_children():
            child.destroy()
        for row, item in enumerate(items):
            tk.Label(self.health_box, text="●", fg=STATE_COLORS.get(item.state, MUTED), bg=SURFACE, font=FONT).grid(
                row=row, column=0, padx=(14, 6), pady=6)
            tk.Label(self.health_box, text=item.name, bg=SURFACE, fg=TEXT, font=FONT_BOLD, anchor="w", width=32).grid(
                row=row, column=1, sticky="w")
            tk.Label(self.health_box, text=item.text, bg=SURFACE, fg=MUTED, font=FONT, anchor="w").grid(
                row=row, column=2, sticky="w", padx=(0, 14))
        self.health_btn.configure(state="normal", text="Durumu Yenile")


def run():
    root = tk.Tk()
    KazenApp(root)
    root.mainloop()
