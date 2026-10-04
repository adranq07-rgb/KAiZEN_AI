"""KAİZEN Desktop -- işletim sistemi yardımcıları (dosyayı aç / klasörde göster / sürükle-bırak).

Sürükle-bırak yeni paket GEREKTİRMEZ: Windows WM_DROPFILES mesajı ctypes ile yakalanır
(tkinterdnd2 / windnd kullanılmaz). Kurulamazsa (Windows dışı, ctypes hatası) False döner ve
UI 'Dosya Ekle' düğmesiyle çalışmaya devam eder -- sessizce yutulmaz, UI uyarı gösterir."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_path(path):
    """Dosyayı varsayılan uygulamayla açar. -> (ok, hata)"""
    p = Path(str(path))
    if not p.exists():
        return False, f"Dosya bulunamadı: {p.name}"
    try:
        if sys.platform == "win32":
            os.startfile(str(p))  # noqa: S606 -- kullanıcının kendi dosyası, tıklama ile
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return True, ""
    except Exception as exc:
        return False, f"Açılamadı: {type(exc).__name__}"


def reveal_in_folder(path):
    p = Path(str(path))
    if not p.exists():
        return False, f"Dosya bulunamadı: {p.name}"
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(p)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p.parent)])
        return True, ""
    except Exception as exc:
        return False, f"Klasör açılamadı: {type(exc).__name__}"


_KEEP_ALIVE = []  # wndproc geri çağrısının çöp toplanmaması için


def install_file_drop(widget, callback):
    """Windows'ta `widget` (tk root) üzerine dosya bırakmayı etkinleştirir. callback(list[str]) UI
    iş parçacığında çağrılır. -> True/False"""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
        GWL_WNDPROC, WM_DROPFILES = -4, 0x0233
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        get_long = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
        set_long = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
        get_long.restype, get_long.argtypes = ctypes.c_void_p, [wintypes.HWND, ctypes.c_int]
        set_long.restype, set_long.argtypes = ctypes.c_void_p, [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        user32.CallWindowProcW.restype = LRESULT
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        shell32.DragFinish.argtypes = [ctypes.c_void_p]
        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]

        widget.update_idletasks()
        hwnd = int(widget.winfo_id())
        old_proc = get_long(hwnd, GWL_WNDPROC)

        def handler(h, msg, wparam, lparam):
            if msg == WM_DROPFILES:
                try:
                    count = shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
                    paths = []
                    for i in range(count):
                        length = shell32.DragQueryFileW(wparam, i, None, 0)
                        buf = ctypes.create_unicode_buffer(length + 1)
                        shell32.DragQueryFileW(wparam, i, buf, length + 1)
                        paths.append(buf.value)
                    shell32.DragFinish(wparam)
                    callback(paths)
                except Exception:
                    pass
                return 0
            return user32.CallWindowProcW(old_proc, h, msg, wparam, lparam)

        proc = WNDPROC(handler)
        _KEEP_ALIVE.append(proc)
        set_long(hwnd, GWL_WNDPROC, ctypes.cast(proc, ctypes.c_void_p))
        shell32.DragAcceptFiles(hwnd, True)
        return True
    except Exception:
        return False
