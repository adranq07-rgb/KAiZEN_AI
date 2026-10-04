"""Kaizen-1 must remain usable without the retired graph-memory integration."""
import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_production_has_no_cognee_integration():
    forbidden = {'remember_experience', 'recall_experience', '_ensure_experience_workers',
                 '_experience_worker_loop', '_record_experience_write', 'experience_stats'}
    for folder in ('core', 'memory', 'accounting', 'learning', 'desktop', 'research', 'search', 'tools'):
        for path in (ROOT / folder).rglob('*.py'):
            if path.name == 'cognee_memory.py':  # Preserved inactive legacy, never imported.
                continue
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert not any('cognee' in a.name.lower() for a in node.names), path
                if isinstance(node, ast.ImportFrom):
                    assert 'cognee' not in (node.module or '').lower(), path
                if isinstance(node, ast.Call):
                    name = getattr(node.func, 'attr', getattr(node.func, 'id', ''))
                    assert name not in forbidden and name != 'CogneeMemory', (path, name)
    config = json.loads((ROOT/'config/Kaizen.json').read_text(encoding='utf-8-sig'))
    assert 'cognee' not in config.get('memory', {})
    assert 'cognee==' not in (ROOT/'requirements.txt').read_text(encoding='utf-8')


def test_engine_never_imports_or_uses_retired_memory():
    # A fresh interpreter rejects even the legacy integration import. This catches
    # dynamic imports that the static source guard cannot see.
    script = '''
import sys, threading
from pathlib import Path
class Guard:
    def find_spec(self, fullname, *args):
        if fullname == "cognee" or fullname.startswith("cognee.") or fullname == "memory.cognee_memory":
            raise AssertionError(fullname)
sys.meta_path.insert(0, Guard())
from core.engine import KaizenEngine
from config.config_manager import ConfigManager
class Poison:
    def __getattr__(self, name): raise AssertionError("retired memory used: " + name)
c=ConfigManager()
c.config["model"]["provider"]="offline"
c.config["retrieval"]["hybrid_enabled"]=False
c.config.setdefault("memory", {})["cognee"]={"enabled": True, "recall_timeout": 60}
root=Path(sys.argv[1])
engine=KaizenEngine(data_dir=root/"data", log_dir=root/"logs", config=c, experience_memory=Poison())
assert not hasattr(engine.brain.brain, "experience")
assert not hasattr(engine.brain.brain, "_experience_queue")
assert "19" in engine.cevap_ver("12 + 7")
assert "153" in engine.cevap_ver("Vadeli mal aldım. Muhasebe açısından ne oldu?")
answer=engine.cevap_ver("Excel bilinmeyen zebra hücre işlemi nedir?")
assert "geçmiş deneyim" not in answer and "Cognee" not in answer
assert "Cognee" not in engine.cevap_ver("durum")
assert engine.reflection_store is not None and engine.runtime_learning is not None
assert engine.shutdown()
assert threading.active_count() == 1
assert not any("cognee" in name for name in sys.modules)
'''
    with tempfile.TemporaryDirectory() as folder:
        result = subprocess.run([sys.executable, '-c', script, folder], cwd=ROOT,
                                capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')


if __name__ == '__main__':
    test_production_has_no_cognee_integration()
    test_engine_never_imports_or_uses_retired_memory()
