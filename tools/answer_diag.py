"""Cevap-verme tanisi: research zinciri ayrintisi + normal muhasebe sorusu. Salt-okunur, izole data/log."""
import json, sys, time, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
OUT = ROOT / "artifacts" / "repair_20261003"; OUT.mkdir(parents=True, exist_ok=True)
R = {}
from config.config_manager import ConfigManager
from accounting.retriever import Retriever
cfg = ConfigManager()
try:
    from research.engine import run_research
    from research.scrapling_adapter import get_adapter
    from search.searxng_provider import SearXNGProvider
    q = "2026 yılı gelir vergisi tarifesinde ilk dilimin üst sınırı ve oranı nedir?"
    res = run_research(q, SearXNGProvider(base_url=cfg.get("research", "base_url", "http://127.0.0.1:8890")), get_adapter())
    R["status"] = res.status; R["search_health"] = res.search_health; R["subquestions"] = list(res.subquestions)
    R["missing_information"] = list(res.missing_information); R["conflicts"] = list(res.conflicts)
    R["claims"] = [{"text": c.text, "status": c.status, "value": c.value, "period": c.period, "ev": list(c.supporting_evidence_ids)} for c in res.claims]
    R["evidence"] = [{"id": e.evidence_id, "sub": e.subquestion[-40:], "url": e.url[:140], "official": e.official, "period": e.period,
                      "fetch": e.fetch_status, "real": e.has_real_content(), "passage": (e.passage or "")[:420],
                      "cov_q": round(Retriever.coverage(q, e.passage or ""), 2), "phrase_q": Retriever.phrase_ok(q, e.passage or "", window=12)}
                     for e in res.evidence]
except Exception as exc:
    R["research_error"] = f"{type(exc).__name__}: {exc}"; R["tb"] = traceback.format_exc()[-800:]
try:
    from core.engine import KaizenEngine
    from tests.doubles import NullExperienceMemory
    e = KaizenEngine(data_dir=OUT / "diag_data", log_dir=OUT / "diag_logs", config=cfg, experience_memory=NullExperienceMemory())
    for key, msg in (("normal_vadeli", "Vadeli mal aldım, muhasebe kaydı nasıl olur?"),
                     ("normal_kavram", "Amortisman nedir ve nasıl hesaplanır?"),
                     ("normal_tutarli", "10.000 TL + KDV vadeli mal aldım, kaydı yaz.")):
        t0 = time.perf_counter(); a = e.cevap_ver(msg); t = e.brain.last_trace
        R[key] = {"answer": a[:700], "route": t.route, "used_model": t.used_model, "used_research": t.used_research,
                  "refusal_reason": t.refusal_reason, "needs_current": t.needs_current_data, "sec": round(time.perf_counter() - t0, 1)}
    e.shutdown()
except Exception as exc:
    R["engine_error"] = f"{type(exc).__name__}: {exc}"; R["tb2"] = traceback.format_exc()[-800:]
(OUT / "answer_diag.json").write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding="utf8")
print("DONE")
