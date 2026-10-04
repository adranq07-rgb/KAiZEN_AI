from datetime import datetime
from pathlib import Path


class KaizenLogger:
    def __init__(self, log_dir=None):
        self.project_dir = Path(__file__).resolve().parent.parent

        if log_dir is None:
            log_dir = self.project_dir / "logs"

        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "kaizen.log"

        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, level, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        line = f"[{timestamp}] [{level.upper()}] {message}\n"

        # SAĞLAMLIK (2026-09-25, gerçek PC UAT bulgusu -- BrainManager arka plan deneyim
        # worker'ı bir kere kaybolan bir log dizinine yazmaya çalışınca FileNotFoundError
        # fırlatıyordu, ve bu istisnayı yakalayan kodun KENDİSİ de tekrar loglamaya çalışınca
        # AYNI hatayı İKİNCİ KEZ üretip çağırana sızdırıyordu). Loglama, tanım gereği
        # "best-effort" bir yan işlemdir -- çağıranın ana iş akışını ASLA bozmamalı/çökertmemeli.
        # Bu düzeltme, işin ASIL kök nedeni olan worker lifecycle sorununun (bkz.
        # memory/brain_manager.py::BrainManager.shutdown) YERİNE değil, ONA EK bir savunma
        # katmanıdır -- log dizini gerçek üründe de (ör. bir temizlik betiği, antivirüs,
        # kullanıcının elle silmesi) her an ortadan kalkabilir.
        try:
            with open(self.log_file, "a", encoding="utf-8") as file:
                file.write(line)
        except OSError:
            # Dizin muhtemelen runtime sırasında silindi -- bir kez yeniden oluşturmayı dene;
            # bu da başarısız olursa (disk salt-okunur, dizin kalıcı olarak gitmiş, vb.)
            # sessizce vazgeç. Loglama HİÇBİR ZAMAN çağıranı çökertmemeli.
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                with open(self.log_file, "a", encoding="utf-8") as file:
                    file.write(line)
            except OSError:
                pass

    def info(self, message):
        self.log("INFO", message)

    def warning(self, message):
        self.log("WARNING", message)

    def error(self, message):
        self.log("ERROR", message)
