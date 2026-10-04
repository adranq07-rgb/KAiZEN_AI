import json
from pathlib import Path


class ConfigManager:
    def __init__(self):
        self.project_dir = Path(__file__).resolve().parent.parent
        self.config_file = self.project_dir / "config" / "Kaizen.json"
        self.config = self._load()

    def _load(self):
        if not self.config_file.exists():
            raise FileNotFoundError("Kaizen config dosyasi bulunamadi.")

        with open(self.config_file, "r", encoding="utf-8") as file:
            return json.load(file)

    def get(self, section, key, default=None):
        return self.config.get(section, {}).get(key, default)

    def cloud_allowed(self):
        return self.get("runtime", "cloud_allowed", False)

    def local_first(self):
        return self.get("runtime", "local_first", True)

    def learning_brain_enabled(self):
        """Faz C / madde 13 (C4): varsayilan KAPALI (False). Acmak/kapatmak tek satirlik
        config/Kaizen.json degisikligi -- kod degismez (bkz. core/engine.py, core/kaizen_brain.py)."""
        return bool(self.get("learning", "learning_brain_enabled", False))

    def research_engine_enabled(self):
        """Is Emri #2, Faz 28-31 (madde 28-31): varsayilan KAPALI (False), learning_brain_enabled
        ile AYNI disiplin. Acmak/kapatmak tek satirlik config/Kaizen.json degisikligi -- kod
        degismez (bkz. core/engine.py, core/kaizen_brain.py)."""
        return bool(self.get("research", "research_engine_enabled", False))

    def experience_lifecycle_enabled(self):
        """Learning Loop fazi: Reflection/Experience yasam dongusu (cevap sonrasi yapisal
        deneyim kaydi + onayla:/duzelt: geri bildirimi). Varsayilan KAPALI (kod seviyesinde);
        config/Kaizen.json -> learning.experience_lifecycle_enabled ile acilir. Yalniz YAPI/
        META kaydeder, FACT uretmez."""
        return bool(self.get("learning", "experience_lifecycle_enabled", False))

    def experience_advice_enabled(self):
        """Onayli (reusable) deneyimden SUREC ipucu (asla FACT). Varsayilan KAPALI; config/
        Kaizen.json -> learning.experience_advice_enabled."""
        return bool(self.get("learning", "experience_advice_enabled", False))

    def hybrid_retrieval_enabled(self):
        """TAM ENTEGRASYON FAZI, Bolum 3: bge-m3 semantik yeniden-siralama (hybrid retrieval).
        Varsayilan KAPALI (False), digerleriyle AYNI disiplin. Acikken bile yalniz zaten
        `accounting/retriever.py::_site_evidence` lexical kapisindan GECMIS kanitlar arasinda
        yeniden siralama/fusion yapar -- kapiyi asla atlamaz veya zayiflatmaz. config/Kaizen.json
        -> retrieval.hybrid_enabled ile acilir."""
        return bool(self.get("retrieval", "hybrid_enabled", False))
