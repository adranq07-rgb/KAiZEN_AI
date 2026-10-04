"""KAZEN-1 broken-connection repair: tek seferlik GERCEK runtime kabul kontrolu.
Sirasiyla: SearXNG -> Research chain (1 soru) -> Model -> BGE-M3 retrieval.
Mock yok. Izole gecici data/log dizini kullanir (gercek data/ ve logs/'a dokunmaz).
Sir yazdirmaz: env degiskenlerinin yalniz ADI + var/yok bilgisi raporlanir."""
import json, os, sys, time, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "artifacts" / "repair_20261003"
OUT.mkdir(parents=True, exist_ok=True)
R = {}

def step(name):
    def deco(fn):
        t = time.perf_counter()
        try:
            R[name] = fn()
        except Exception as exc:
            R[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc()[-600:]}
        R[name]["seconds"] = round(time.perf_counter() - t, 1)
        print(name, json.dumps({k: v for k, v in R[name].items() if k != "tb"}, ensure_ascii=False, default=str)[:700], flush=True)
        return fn
    return deco

from config.config_manager import ConfigManager
cfg = ConfigManager()
base = cfg.get("research", "base_url", "http://127.0.0.1:8890")

@step("1_searxng")
def _():
    from search.searxng_provider import SearXNGProvider
    p = SearXNGProvider(base_url=base)
    o = p.search("gelir vergisi tarifesi 2026")
    return {"ok": len(o.results) > 0, "base_url": base, "status": str(o.status), "results": len(o.results),
            "first_url": o.results[0].url if o.results else None, "health": str(p.health.state)}

engine = None
try:
    from core.engine import KaizenEngine
    from tests.doubles import NullExperienceMemory
    engine = KaizenEngine(data_dir=OUT / "data", log_dir=OUT / "logs", config=cfg, experience_memory=NullExperienceMemory())
except Exception as exc:
    R["engine_build"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

@step("2_research_chain")
def _():
    q = "2026 yılı gelir vergisi tarifesinde ilk dilimin üst sınırı ve oranı nedir?"
    ans = engine.cevap_ver(q)
    t = engine.brain.last_trace.to_dict()
    keys = ["route", "used_facts", "used_memory", "used_model", "used_research", "research_status", "search_provider",
            "search_health", "query_count", "result_count", "fetched_count", "evidence_count", "official_evidence_count",
            "consensus_status", "refusal_reason", "decision", "confidence", "scrapling_attempted", "scrapling_success"]
    tr = {k: t.get(k) for k in keys}
    return {"ok": bool(t.get("used_research")) and not t.get("used_facts") and (t.get("result_count") or 0) > 0,
            "question": q, "answer": ans[:600], "trace": tr}

@step("3_model")
def _():
    import urllib.request
    envs = {n: bool(os.environ.get(n)) for n in ("NVIDIA_API_KEY", "OPENCODE_API_KEY", "OPENROUTER_API_KEY", "NGC_API_KEY")}
    ans = engine.cevap_ver("Merhaba, bir cümleyle kendini tanıt.")
    t = engine.brain.last_trace
    models = json.loads(urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5).read())["models"]
    return {"ok": bool(t.used_model), "used_model": bool(t.used_model), "answer": ans[:300],
            "configured_provider": cfg.get("model", "provider"), "configured_local_model": cfg.get("model", "local", {}).get("model_name"),
            "ollama_models": [m["name"] for m in models], "nemotron_in_ollama": any("nemotron" in m["name"].lower() for m in models),
            "env_var_presence(names only)": envs}

@step("3b_nemotron_direct")
def _():
    import copy
    from core.ai.provider_factory import build_provider
    name = cfg.get("model", "nemotron", {}).get("api_key_env", "NGC_API_KEY")
    if not os.environ.get(name):
        return {"ok": False, "blocked": f"{name} ortam degiskeni bu surecte yok (deger yazdirilmaz)"}
    c2 = copy.deepcopy(cfg); c2.config["model"]["provider"] = "nemotron"; c2.config["model"]["fallback"] = []
    a = build_provider(c2).ask("Tek cümleyle: KDV nedir?")
    return {"ok": not a.startswith("Kaizen:"), "model": c2.config["model"]["nemotron"]["model_name"], "answer": a[:300]}

@step("4_bge_m3_retrieval")
def _():
    from core.ai.embedding_client import OllamaEmbeddingClient
    from accounting.retriever import Evidence
    c = OllamaEmbeddingClient(base_url=cfg.get("retrieval", "base_url"), model_name=cfg.get("retrieval", "model_name"), timeout=90)
    v = c.embed("KDV indirimi nasıl yapılır")
    r = engine.brain.brain.retriever
    items = [Evidence("site", "hava", "Yarın İstanbul'da yağmur ve rüzgar bekleniyor."),
             Evidence("site", "kdv", "İndirilecek KDV, mal ve hizmet alımlarında ödenen katma değer vergisinin beyannamede indirilmesidir."),
             Evidence("site", "futbol", "Maçın ilk yarısı 1-0 sona erdi.")]
    r.hybrid_enabled = True
    ranked = r._semantic_rerank("Alışlarda ödenen KDV beyannamede nasıl indirim konusu yapılır?", items)
    return {"ok": bool(v) and r.last_metrics.get("semantic_used") is True and ranked[0].label == "kdv",
            "embedding_dim": len(v) if v else None, "retrieval_mode": r.last_metrics.get("retrieval_mode"),
            "semantic_order": list(r.last_metrics.get("semantic_order", ())), "fallback_reason": r.last_metrics.get("fallback_reason")}

if engine:
    try: engine.shutdown()
    except Exception: pass
(OUT / "repair_acceptance_result.json").write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding="utf8")
print("DONE ->", OUT / "repair_acceptance_result.json")
