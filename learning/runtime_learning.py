"""Outcome-derived procedural policies. No answers, amounts or factual claims are stored.

The catalog defines allowed actions, not learned answers. Only observed executions
create policies. Independent question hashes support them; feedback is append-only.
Verified tool/research execution or explicit approval can support a policy. A policy
can only choose a process; facts and deterministic tools always run first.
"""
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from learning.question_profile import profile_question
from learning.reflection_lifecycle import question_key, _derive_strategy
from learning.strategy_advisor import StrategyAdvice
from learning.strategy_catalog import STRATEGIES, strategy_applies_to


def _now():
    return datetime.now(timezone.utc).isoformat()


class RuntimeLearning:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY, question_key TEXT NOT NULL, domain TEXT NOT NULL,
                    kind TEXT NOT NULL, strategy TEXT NOT NULL, policy_id TEXT,
                    verified INTEGER NOT NULL, positive INTEGER NOT NULL DEFAULT 0,
                    negative INTEGER NOT NULL DEFAULT 0, metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS episode_question ON episodes(question_key, created_at);
                CREATE TABLE IF NOT EXISTS reflections (
                    id TEXT PRIMARY KEY, episode_id TEXT NOT NULL, reason TEXT NOT NULL,
                    next_action TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS policies (
                    id TEXT PRIMARY KEY, domain TEXT NOT NULL, kind TEXT NOT NULL,
                    strategy TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY, episode_id TEXT NOT NULL, positive INTEGER NOT NULL,
                    provenance TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')
            c.commit()

    def _connect(self):
        c = sqlite3.connect(self.db_path, timeout=0.5)
        c.row_factory = sqlite3.Row
        return c

    def observe(self, question, trace, answer_text, research_meta=None):
        profile = profile_question(question, trace.intent or "general", trace.needs_current_data)
        strategy = _derive_strategy(profile, trace.route, research_meta, answer_text, trace.used_research)
        exact = trace.route in {"arithmetic", "calculator", "chart", "journal", "facts"}
        verified = exact or (trace.route == "research" and bool(research_meta)
                             and research_meta.get("status") == "SUPPORTED")
        if exact:
            strategy = "exact_tool_first"
        strategy = strategy or "observe_only"
        pid = None
        if strategy != "observe_only":
            pid = hashlib.sha256(f"{profile.domain}|{profile.kind}|{strategy}".encode()).hexdigest()[:24]
        eid, rid, now = str(uuid4()), str(uuid4()), _now()
        action = ("extractive_first" if strategy in STRATEGIES and not STRATEGIES[strategy]["triggers_research"]
                  else "verify_sources" if strategy in STRATEGIES else "exact_tool_first")
        # Scalar allowlist: never serialize raw question, answer, prompt or exception text.
        metadata = {k: getattr(trace, k) for k in (
            "intent", "route", "confidence", "used_model", "used_research", "model_calls",
            "retrieval_mode", "semantic_used", "cache_hits", "cache_misses", "elapsed_ms",
            "query_count", "fetched_count", "consensus_status", "research_status",
            "strategy_source", "strategy_experience_ids", "latency_breakdown")}
        metadata["outcome"] = "verified" if verified else "refused" if trace.refusal_reason else "unverified"
        reason = ("verified_execution" if verified else "missing_evidence" if trace.refusal_reason
                  else "requires_outcome_validation")
        with closing(self._connect()) as c:
            c.execute("INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (eid, question_key(question), profile.domain, profile.kind, strategy, pid,
                       int(verified), 0, 0, json.dumps(metadata), now, now))
            c.execute("INSERT INTO reflections VALUES (?,?,?,?,?)", (rid, eid, reason, action, now))
            if pid:
                c.execute("INSERT INTO policies VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at",
                          (pid, profile.domain, profile.kind, strategy, action, now, now))
            c.commit()
        return {"experience_id": eid, "reflection_id": rid, "learned_principle_id": pid,
                "strategy": strategy, "outcome": metadata["outcome"]}

    def feedback(self, question, positive):
        with closing(self._connect()) as c:
            row = c.execute("SELECT * FROM episodes WHERE question_key=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                            (question_key(question),)).fetchone()
            if row is None:
                return {"applied": False}
            now = _now()
            c.execute("UPDATE episodes SET positive=positive+?, negative=negative+?, updated_at=? WHERE id=?",
                      (int(positive), int(not positive), now, row["id"]))
            c.execute("INSERT INTO feedback VALUES (?,?,?,?,?)",
                      (str(uuid4()), row["id"], int(positive), "user_approval" if positive else "user_correction", now))
            c.execute("UPDATE policies SET updated_at=? WHERE id=?", (now, row["policy_id"]))
            c.commit()
        return {"applied": True, "record_id": row["id"], "feedback": "positive" if positive else "negative",
                "reusable": bool(positive and not row["negative"] and row["policy_id"])}

    def policies(self, domain, kind):
        with closing(self._connect()) as c:
            policies = c.execute("SELECT * FROM policies WHERE domain=? AND kind=?", (domain, kind)).fetchall()
            result = []
            for policy in policies:
                episodes = c.execute("SELECT * FROM episodes WHERE policy_id=?", (policy["id"],)).fetchall()
                # A repeated approval or repeated wording cannot manufacture corroboration.
                supports = {e["question_key"] for e in episodes if (e["verified"] or e["positive"]) and not e["negative"]}
                contradictions = {e["question_key"] for e in episodes if e["negative"]}
                supports -= contradictions
                net = len(supports) - 2 * len(contradictions)
                result.append({**dict(policy), "support": len(supports), "contradictions": len(contradictions),
                    "confidence": "high" if net >= 3 else "medium" if net >= 1 else "low",
                    "active": net >= 1, "net_score": net,
                    "experience_ids": tuple(e["id"] for e in episodes if e["question_key"] in supports),
                    "provenance": "observed_outcomes"})
        return result

    def advise(self, question, domain, needs_current=False):
        profile = profile_question(question, domain, needs_current)
        candidates = [p for p in self.policies(domain, profile.kind)
                      if p["active"] and strategy_applies_to(p["strategy"], profile.kind)]
        if not candidates:
            return StrategyAdvice(rejected_reason="no_validated_runtime_policy")
        best = max(candidates, key=lambda p: p["net_score"])
        spec = STRATEGIES[best["strategy"]]
        return StrategyAdvice(strategy_kind=best["strategy"], guide=spec["guide"],
            confidence=best["confidence"], support=best["support"], net_score=best["net_score"],
            triggers_research=spec["triggers_research"], question_kind=profile.kind,
            source="learned_principle", policy_id=best["id"], experience_ids=best["experience_ids"],
            action=best["action"])

    def status(self):
        with closing(self._connect()) as c:
            episodes = c.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            reflections = c.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
            scopes = c.execute("SELECT DISTINCT domain, kind FROM policies").fetchall()
        active = sum(p["active"] for scope in scopes for p in self.policies(*scope))
        return {"episodes": episodes, "reflections": reflections, "active_policies": active}
