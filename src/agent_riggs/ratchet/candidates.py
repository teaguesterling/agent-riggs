"""Identify ratchet promotion candidates from cross-session data."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from agent_riggs.config import RatchetConfig
from agent_riggs.store import Store

@dataclass
class Candidate:
    candidate_type: str
    candidate_key: str
    evidence: dict[str, Any]
    recommendation: str

def find_tool_candidates(store, project, config):
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.lookback_days)
    rows = store.execute("""
        SELECT metadata, count(*) AS frequency, count(DISTINCT session_id) AS sessions,
               round(avg(CASE WHEN tool_success THEN 1.0 ELSE 0.0 END), 2) AS success_rate
        FROM turns WHERE project = ? AND tool_name = 'Bash'
          AND timestamp > ?
        GROUP BY metadata HAVING count(*) >= ? AND count(DISTINCT session_id) >= ?
        ORDER BY frequency DESC""", [project, cutoff, config.min_frequency, config.min_sessions]).fetchall()
    candidates = []
    for row in rows:
        metadata_str, frequency, sessions, success_rate = row
        if success_rate < config.min_success_rate:
            continue
        alternative = _find_alternative(metadata_str)
        if alternative is None:
            continue
        candidates.append(Candidate(candidate_type="tool_promotion",
            candidate_key=f"bash-to-{alternative.lower().replace(' ', '-')}",
            evidence={"frequency": frequency, "sessions": sessions, "success_rate": success_rate, "command_pattern": metadata_str},
            recommendation=f"Graduate {alternative} interceptor"))
    return candidates

def find_constraint_candidates(store, project, config):
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.lookback_days)
    rows = store.execute("""
        SELECT failure_category, tool_name, mode, count(*) AS occurrences,
               count(DISTINCT session_id) AS sessions_affected,
               round(avg(trust_at_failure), 2) AS avg_trust
        FROM failure_stream WHERE project = ?
          AND occurred_at > ?
        GROUP BY failure_category, tool_name, mode
        HAVING count(*) >= ? ORDER BY occurrences DESC""",
        [project, cutoff, config.min_frequency]).fetchall()
    candidates = []
    for row in rows:
        category, tool, mode, occurrences, sessions, avg_trust = row
        severity = "systemic" if sessions >= config.min_sessions else "frequent" if occurrences >= config.min_frequency * 2 else "occasional"
        candidates.append(Candidate(candidate_type="constraint_promotion",
            candidate_key=f"{category}-{tool or 'unknown'}-{mode or 'any'}",
            evidence={"occurrences": occurrences, "sessions_affected": sessions, "avg_trust": avg_trust, "severity": severity},
            recommendation=_constraint_recommendation(category, tool, mode)))
    return candidates

def _find_alternative(metadata_str):
    s = metadata_str.lower()
    if "grep" in s and ("def " in s or "class " in s): return "FindDefinitions"
    if "pytest" in s: return "blq run test"
    if "git add" in s and "git commit" in s: return "jetsam save"
    if "git push" in s: return "jetsam sync"
    return None

def _constraint_recommendation(category, tool, mode):
    parts = [f"Repeated {category}"]
    if tool: parts.append(f"on {tool}")
    if mode: parts.append(f"in {mode} mode")
    parts.append("— review configuration or add documentation")
    return " ".join(parts)
