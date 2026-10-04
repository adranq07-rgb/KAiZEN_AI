"""Real-PC checks with isolated stores and incremental reports for restart recovery.

Run as a module: python -B -m tools.learning_brain_uat --stage runtime|research
No production data or service configuration is changed.
"""
import argparse
import contextlib
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from config.config_manager import ConfigManager
from core.engine import KaizenEngine
from core.ai.local_provider import LocalProvider
from core.ai.offline_provider import OfflineProvider
from core.ai.embedding_client import OllamaEmbeddingClient
from core.ai.embedding_cache import EmbeddingCache
from accounting.retriever import Evidence, Retriever

ROOT = Path(__file__).resolve().parent.parent


class Report:
    def __init__(self, stage):
        self.stage = stage
        self.root = ROOT / "artifacts" / ("learning_brain_v1_" + stage + "_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        self.root.mkdir(parents=True, exist_ok=False)
        self.data = {"started_at": datetime.now(timezone.utc).isoformat(), "stage": stage, "checks": {}}

    def record(self, name, ok, **observed):
        self.data["checks"][name] = {"ok": bool(ok), **observed}
        self.save()
        print(name, "PASS" if ok else "FAIL", flush=True)

    def save(self):
        (self.root / "report.json").write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")


def runtime(report):
    config = ConfigManager()
    local = LocalProvider(model_name="llama3.2:3b", timeout=120)
    engine = KaizenEngine(data_dir=report.root / "data", log_dir=report.root / "logs",
                          provider=local, config=config)
    try:
        answer = engine.cevap_ver("12 + 7")
        trace = engine.brain.last_trace.to_dict()
        report.record("A_deterministic", "19" in answer and trace["model_calls"] == 0,
                      answer=answer, trace=trace)
        answer = engine.cevap_ver("191 hesap kodu nedir?")
        report.record("B_accounting", engine.brain.last_route == "chart", answer=answer,
                      trace=engine.brain.last_trace.to_dict())
        first = "Stok değerleme yöntemleri nedir?"
        answer = engine.cevap_ver(first)
        first_trace = engine.brain.last_trace.to_dict()
        report.record("GHI_experience_reflection_policy", all(first_trace[k] for k in
                      ("experience_id", "reflection_id", "learned_principle_id")),
                      answer=answer, trace=first_trace)
        approval = engine.cevap_ver("onayla: " + first)
        report.record("L_approval", bool(engine.brain.last_feedback_effect and engine.brain.last_feedback_effect.get("reusable")),
                      response=approval)
        answer = engine.cevap_ver("Mizan nedir?")
        second_trace = engine.brain.last_trace.to_dict()
        report.record("J_transfer", second_trace["strategy_source"] == "learned_principle"
                      and bool(second_trace["strategy_experience_ids"]) and second_trace["route"] == "memory_extractive",
                      answer=answer, first_model_calls=first_trace["model_calls"],
                      second_model_calls=second_trace["model_calls"], trace=second_trace)
        correction = engine.cevap_ver("düzelt: " + first + " => Önce kanıtı doğrula, uygun yöntemi sonra seç.")
        advice = engine.runtime_learning.advise("Mizan nedir?", "accounting")
        report.record("K_correction", not advice.applied, response=correction)
        # Real socket refusal, scoped to this engine; existing services are left running.
        engine.brain._search_provider.base_url = "http://127.0.0.1:9"
        engine.brain._search_provider.timeout = 0.3
        engine.brain._search_provider.max_attempts = 1
        question = "2026 SGK prim tavanı nedir?"
        engine.accounting_agent.learn(question, "", "999.999.999 TL")
        answer = engine.cevap_ver(question)
        trace = engine.brain.last_trace.to_dict()
        report.record("CM_current_fact_safety", "999.999.999" not in answer
                      and trace["route"] == "not_found_offline" and trace["model_calls"] == 0,
                      answer=answer, trace=trace)
        local.base_url = "http://127.0.0.1:9/v1"
        local.timeout = 0.3
        answer = engine.cevap_ver("Stok değerleme yöntemlerini anlatır mısın?")
        report.record("E_local_model_unreachable", bool(answer) and engine.brain.last_route == "memory_extractive",
                      trace=engine.brain.last_trace.to_dict())
        report.record("N_trace", bool(trace["experience_id"] and trace["reflection_id"]
                      and trace["verification_result"] and trace["elapsed_ms"] is not None), trace=trace)
    finally:
        report.record("shutdown", engine.shutdown())

    client = OllamaEmbeddingClient(timeout=90)
    cache = EmbeddingCache(report.root / "embedding_cache.sqlite3")
    retriever = Retriever(object(), accounting_brain=object(), embedding_client=client,
                          embedding_cache=cache, hybrid_enabled=True)
    items = [Evidence("site", "source_a", "Muhasebede dönemsellik gelir ve giderin ait olduğu dönemi esas alır."),
             Evidence("site", "source_b", "Muhasebede dönemsellik ilkesi ödeme ve belge tarihinden bağımsız değerlendirilir.")]
    times = []
    metrics = []
    for _ in range(2):
        retriever.last_metrics = {}
        started = time.perf_counter()
        ranked = retriever._semantic_rerank("Muhasebede dönemsellik", items)
        times.append(round((time.perf_counter() - started) * 1000, 3))
        metrics.append(dict(retriever.last_metrics))
    report.record("BGE_real_and_cache", all(m.get("semantic_used") for m in metrics)
                  and metrics[1].get("cache_hits") == 3, elapsed_ms=times, metrics=metrics)
    retriever._embedding_client = OllamaEmbeddingClient(base_url="http://127.0.0.1:9", timeout=0.3)
    retriever._embedding_cache = None
    report.record("D_embedding_unreachable", retriever._semantic_rerank("uncached", items) == items,
                  metrics=retriever.last_metrics)


def research(report):
    from research.engine import run_research
    from research.fetcher import SafeFetcher
    from research.summary import summarize_research
    from search.searxng_provider import SearXNGProvider
    search = SearXNGProvider(timeout=12, max_attempts=1)
    started = time.perf_counter()
    result = run_research("Muhasebede dönemsellik kavramı nedir?", search, SafeFetcher(timeout=12))
    meta = summarize_research(result)
    report.record("research_real", result.status == "SUPPORTED" and bool(result.verified_claims),
                  meta=meta, elapsed_s=round(time.perf_counter()-started, 3))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("runtime", "research"), required=True)
    args = parser.parse_args()
    report = Report(args.stage)
    print("Report:", report.root / "report.json", flush=True)
    try:
        globals()[args.stage](report)
    except Exception as exc:
        import traceback
        report.record("unexpected_error", False, error=type(exc).__name__, traceback=traceback.format_exc())
    report.data["finished_at"] = datetime.now(timezone.utc).isoformat()
    report.data["passed"] = all(check["ok"] for check in report.data["checks"].values())
    report.save()
    return int(not report.data["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
