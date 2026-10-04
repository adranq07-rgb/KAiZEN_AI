"""KAİZEN masaüstü uygulaması -- giriş noktası (geliştirme modu).

Çalıştırma:  Kazen_Baslat.bat   (veya  .venv\Scripts\python.exe kazen_desktop.py)
Backend DEĞİŞMEZ: arayüz yalnız KaizenEngine.cevap_ver() çağırır. Eski arayüz (desktop_app.py,
Kaizen_Baslat.bat) olduğu gibi durur."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from desktop.kazen_ui import run  # noqa: E402

if __name__ == "__main__":
    run()
