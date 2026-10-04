"""KAİZEN Desktop ilk kabul: arayüzün KULLANDIĞI denetleyici (KazenController) + GERÇEK KaizenEngine.
Pencere açmaz; kullanıcının UI'da yazacağı mesajların aynısını aynı yoldan gönderir.
TEST 1 'Sen kimsin?'  TEST 2 vadeli mal kaydı  TEST 3 gerçek dosya (ft.pdf) muhasebe analizi.
Sır yazdırmaz. Sonuç: artifacts/kazen_ui_20261004/ui_acceptance_result.json"""
import json
import queue
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "artifacts" / "kazen_ui_20261004"
OUT.mkdir(parents=True, exist_ok=True)

from desktop.chat_store import ChatStore  # noqa: E402
from desktop.controller import KazenController  # noqa: E402

TESTS = [
    ("TEST1_kimsin", "Sen kimsin?", []),
    ("TEST2_vadeli_mal", "Vadeli 100.000 TL + %20 KDV ticari mal aldım. Kaydı nedir?", []),
    ("TEST3_gercek_dosya", "Bu faturayı muhasebe açısından analiz et", [str(ROOT / "ft.pdf")]),
]


def drain(ctl, stop, timeout):
    events, end = [], time.time() + timeout
    while time.time() < end:
        try:
            events.append(ctl.events.get(timeout=0.5))
        except queue.Empty:
            continue
        if events[-1][0] in stop:
            break
    return events


def main():
    ctl = KazenController(store=ChatStore(Path(tempfile.mkdtemp()) / "ui_test.json"))
    result = {}
    t0 = time.perf_counter()
    ctl.start_engine()
    ev = drain(ctl, {"engine_ready", "engine_error"}, 180)
    result["engine"] = {"event": ev[-1][0] if ev else "timeout", "seconds": round(time.perf_counter() - t0, 1)}
    print("engine", result["engine"], flush=True)
    if not ev or ev[-1][0] != "engine_ready":
        result["engine"]["error"] = str(ev[-1][1]) if ev else "timeout"
    else:
        for name, text, files in TESTS:
            started = time.perf_counter()
            if files and not Path(files[0]).exists():
                result[name] = {"ok": False, "error": f"dosya yok: {files[0]}"}
                continue
            ctl.submit(text, files)
            events = drain(ctl, {"answer", "error", "attach_error"}, 600)
            last = events[-1] if events else ("timeout", None)
            item = {"message": text, "files": [Path(f).name for f in files],
                    "status_shown": [e[1] for e in events if e[0] == "status" and e[1]],
                    "seconds": round(time.perf_counter() - started, 1), "event": last[0]}
            if last[0] == "answer":
                view, _ = last[1]
                item.update(ok=True, answer=view.body, route=view.route_label, sources=[(s.label, s.url) for s in view.sources],
                            verification=view.verification, outputs=view.outputs, refusal=view.is_refusal,
                            trace=view.trace_summary)
            else:
                item.update(ok=False, error=str(last[1]))
            result[name] = item
            print(name, "->", item["event"], "|", (item.get("answer") or item.get("error") or "")[:300].replace("\n", " "), flush=True)
            time.sleep(0.5)
    (OUT / "ui_acceptance_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("YAZILDI:", OUT / "ui_acceptance_result.json")


if __name__ == "__main__":
    main()
