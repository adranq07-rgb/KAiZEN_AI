"""Run every module-owned test, without silently omitting new regression modules."""
import contextlib
import importlib
import inspect
import io
import json
import time
from pathlib import Path


def main():
    results = []
    started = time.perf_counter()
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        module = importlib.import_module("tests." + path.stem)
        for name, test in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_") or test.__module__ != module.__name__:
                continue
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    test()
                results.append({"test": path.stem + "." + name, "ok": True})
            except Exception as exc:
                import traceback
                results.append({"test": path.stem + "." + name, "ok": False,
                                "error": type(exc).__name__ + ": " + str(exc)[:1500],
                                "traceback": traceback.format_exc()})
        print(path.stem, "completed", flush=True)
    report = {"total": len(results), "passed": sum(r["ok"] for r in results),
              "elapsed_s": round(time.perf_counter() - started, 3),
              "failures": [r for r in results if not r["ok"]]}
    output_path = Path(__file__).resolve().parent.parent / "artifacts" / "learning_brain_v1_tests.json"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report["failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
