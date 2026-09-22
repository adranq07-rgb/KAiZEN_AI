from pathlib import Path
import shutil


class DevManager:
    def __init__(self):
        self.project_dir = Path(__file__).resolve().parent.parent
        self.workspace = self.project_dir / "dev" / "workspace"

    def prepare_workspace(self):
        self.workspace.mkdir(parents=True, exist_ok=True)
        return self.workspace

    @staticmethod
    def _inside(path, root):
        return path.resolve().is_relative_to(root.resolve())

    def copy_for_testing(self, source):
        source_path = self.project_dir / source

        if not self._inside(source_path, self.project_dir):
            return False, "Kaynak proje klasoru disinda."

        if not source_path.is_file():
            return False, "Kaynak dosya bulunamadi."

        self.prepare_workspace()

        target = self.workspace / source_path.name
        shutil.copy2(source_path, target)

        return True, str(target)

    def promote_to_prod(self, dev_file, destination, approved=False):
        if not approved:
            return False, "PROD aktarimi kullanici onayi gerektiriyor."

        dev_path = self.workspace / dev_file
        destination_path = self.project_dir / destination

        if not self._inside(dev_path, self.workspace):
            return False, "DEV dosyasi calisma alani disinda."

        if not self._inside(destination_path, self.project_dir):
            return False, "Hedef proje klasoru disinda."

        if not dev_path.is_file():
            return False, "DEV dosyasi bulunamadi."

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dev_path, destination_path)

        return True, str(destination_path)

    def clear_workspace(self, approved=False):
        if not approved:
            return False, "DEV calisma alanini temizlemek kullanici onayi gerektiriyor."

        if not self._inside(self.workspace, self.project_dir):
            return False, "DEV calisma alani proje klasoru disinda."

        if self.workspace.exists():
            shutil.rmtree(self.workspace)

        self.prepare_workspace()
        return True, str(self.workspace)
