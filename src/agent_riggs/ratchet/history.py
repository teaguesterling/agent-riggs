"""Ratchet decision history queries."""
from __future__ import annotations
from typing import Any
from agent_riggs.store import Store

def get_history(store, limit=50):
    rows = store.execute("""
        SELECT decided_at, candidate_type, candidate_key, decision, reason, evidence, config_change
        FROM ratchet_decisions ORDER BY decided_at DESC LIMIT ?""", [limit]).fetchall()
    return [{"decided_at": r[0], "candidate_type": r[1], "candidate_key": r[2],
             "decision": r[3], "reason": r[4], "evidence": r[5], "config_change": r[6]} for r in rows]
