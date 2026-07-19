"""Identify ratchet promotion candidates from cross-session data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import duckdb


@dataclass
class Candidate:
    candidate_type: str
    candidate_key: str
    evidence: dict[str, Any]
    recommendation: str


def nudge_heed_summary(store) -> list[dict[str, Any]]:
    """Per-plugin A/B evidence from kibitzer nudge trials.

    Each trial is one eligible bypass: the nudge arm shows whether a
    suggestion changes behavior; the control arm shows the base rate.
    Returns every evaluated plugin (qualifying or not) so the gate is
    inspectable — but only `find_nudge_candidates` surfaces candidates.
    """
    try:
        rows = store.execute(
            """
            SELECT plugin,
                   count(*) FILTER (WHERE arm IN ('nudge', 'control')) AS trials,
                   count(DISTINCT session_id) AS sessions,
                   count(*) FILTER (WHERE arm = 'nudge') AS nudges,
                   count(*) FILTER (WHERE arm = 'nudge' AND heed) AS nudges_heeded,
                   count(*) FILTER (WHERE arm = 'control') AS controls,
                   count(*) FILTER (WHERE arm = 'control' AND heed) AS controls_heeded
            FROM nudge_trials
            GROUP BY plugin
            ORDER BY trials DESC
            """
        ).fetchall()
    except duckdb.Error:
        # No nudge_trials table (store predates it, or no trials file) —
        # degrade gracefully: no evidence, no candidates.
        return []

    summary = []
    for plugin, trials, sessions, nudges, nudges_heeded, controls, controls_heeded in rows:
        heed_rate = nudges_heeded / nudges if nudges else 0.0
        control_rate = controls_heeded / controls if controls else 0.0
        summary.append(
            {
                "plugin": plugin,
                "trials": trials,
                "sessions": sessions,
                "nudges": nudges,
                "nudges_heeded": nudges_heeded,
                "heed_rate": round(heed_rate, 2),
                "controls": controls,
                "controls_heeded": controls_heeded,
                "control_heed_rate": round(control_rate, 2),
                "lift": round(heed_rate - control_rate, 2),
            }
        )
    return summary


def find_nudge_candidates(store, project, config):
    """Tool-promotion candidates gated on *measured* heed, never frequency.

    A plugin's nudge frequency (how often its bypass fires) says nothing
    about whether escalating it changes behavior — that's the
    correlation/causation gap. The gate requires:
      - enough nudge-arm trials (min_nudge_trials),
      - a measured heed rate (min_heed_rate),
      - heed lift over the control arm (min_heed_lift).
    A plugin with 1000 bypasses and zero heeded nudges never surfaces.
    """
    candidates = []
    for s in nudge_heed_summary(store):
        # Frequency leg: necessary but never sufficient.
        if s["trials"] < config.min_frequency or s["sessions"] < config.min_sessions:
            continue
        # Causal leg: measured heed and lift — the actual gate.
        if s["nudges"] < config.min_nudge_trials:
            continue
        if s["heed_rate"] < config.min_heed_rate:
            continue
        if s["lift"] < config.min_heed_lift:
            continue
        candidates.append(
            Candidate(
                candidate_type="nudged_tool_promotion",
                candidate_key=f"nudge-{s['plugin']}",
                evidence=s,
                recommendation=(
                    f"Escalate kibitzer [plugins.{s['plugin']}] mode suggest -> redirect: "
                    f"heed {s['heed_rate']:.0%} vs control {s['control_heed_rate']:.0%} "
                    f"(lift {s['lift']:+.0%}, n={s['nudges']} nudges)"
                ),
            )
        )
    return candidates


def find_constraint_candidates(store, project, config):
    cutoff = datetime.now(UTC) - timedelta(days=config.lookback_days)
    rows = store.execute(
        """
        SELECT failure_category, tool_name, mode, count(*) AS occurrences,
               count(DISTINCT session_id) AS sessions_affected,
               round(avg(trust_at_failure), 2) AS avg_trust
        FROM failure_stream WHERE project = ?
          AND occurred_at > ?
        GROUP BY failure_category, tool_name, mode
        HAVING count(*) >= ? ORDER BY occurrences DESC""",
        [project, cutoff, config.min_frequency],
    ).fetchall()
    candidates = []
    for row in rows:
        category, tool, mode, occurrences, sessions, avg_trust = row
        severity = (
            "systemic"
            if sessions >= config.min_sessions
            else "frequent"
            if occurrences >= config.min_frequency * 2
            else "occasional"
        )
        candidates.append(
            Candidate(
                candidate_type="constraint_promotion",
                candidate_key=f"{category}-{tool or 'unknown'}-{mode or 'any'}",
                evidence={
                    "occurrences": occurrences,
                    "sessions_affected": sessions,
                    "avg_trust": avg_trust,
                    "severity": severity,
                },
                recommendation=_constraint_recommendation(category, tool, mode),
            )
        )
    return candidates


def _constraint_recommendation(category, tool, mode):
    parts = [f"Repeated {category}"]
    if tool:
        parts.append(f"on {tool}")
    if mode:
        parts.append(f"in {mode} mode")
    parts.append("— review configuration or add documentation")
    return " ".join(parts)
