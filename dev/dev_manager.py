from pathlib import Path
import shutil


class DevManager:
    def __init__(self):
        self.project_dir = Path(__file__).resolve().parent.parent
        self.workspace = self.project_dir / "dev" / "workspace"

    def prepare_workspace(self):
        self.workspace.mkdir(parents=True, exist_ok=True)
        return self.workspace

    def copy_for_testing(self, source):
        source_path = self.project_dir / source

        if not source_path.exists():
            return False, "Kaynak dosya bulunamadi."

        self.prepare_workspace()

        target = self.workspace / source_path.name
        shutil.copy2(source_path, target)

        return True, str(target)

    def clear_workspace(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

        self.prepare_workspace()