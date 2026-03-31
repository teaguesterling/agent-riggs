"""Ratchet metrics computation from the store."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RatchetMetrics:
    total_sessions: int
    total_turns: int
    total_failures: int
    failure_rate: float
    ratchet_velocity: int
    structured_tool_fraction: float
    computation_channel_fraction: float
    trust_trajectory_start: float
    trust_trajectory_end: float
    mode_distribution: dict[str, float]

def compute_metrics(store, project, period_days=30):
    session_row = store.execute("""
        SELECT count(*), coalesce(sum(total_failures), 0),
               coalesce(avg(structured_tool_fraction), 0), coalesce(avg(computation_channel_fraction), 0)
        FROM session_summaries WHERE project = ?""", [project]).fetchone()
    total_sessions, total_failures = session_row[0], session_row[1]
    structured_frac, compute_frac = session_row[2], session_row[3]

    turns_row = store.execute("""
        SELECT count(*) FROM turns WHERE project = ?""", [project]).fetchone()
    total_turns = turns_row[0] if turns_row else 0

    failure_rate = total_failures / total_turns if total_turns > 0 else 0.0

    trust_row = store.execute("""
        SELECT first(trust_5 ORDER BY timestamp ASC), last(trust_5 ORDER BY timestamp ASC)
        FROM turns WHERE project = ?""", [project]).fetchone()
    trust_start = trust_row[0] if trust_row and trust_row[0] is not None else 1.0
    trust_end = trust_row[1] if trust_row and trust_row[1] is not None else 1.0

    ratchet_row = store.execute("""
        SELECT count(*) FROM ratchet_decisions WHERE decision = 'promoted'""").fetchone()
    ratchet_velocity = ratchet_row[0] if ratchet_row else 0

    mode_rows = store.execute("""
        SELECT mode, count(*) FROM turns WHERE project = ? AND mode IS NOT NULL
        GROUP BY mode""", [project]).fetchall()
    total_mode_turns = sum(r[1] for r in mode_rows) if mode_rows else 1
    mode_distribution = {r[0]: r[1] / total_mode_turns for r in mode_rows} if mode_rows else {}

    return RatchetMetrics(total_sessions=total_sessions, total_turns=total_turns,
        total_failures=total_failures, failure_rate=failure_rate, ratchet_velocity=ratchet_velocity,
        structured_tool_fraction=structured_frac, computation_channel_fraction=compute_frac,
        trust_trajectory_start=trust_start, trust_trajectory_end=trust_end,
        mode_distribution=mode_distribution)
