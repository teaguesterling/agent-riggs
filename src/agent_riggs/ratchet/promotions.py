"""Apply and record ratchet promotion decisions."""
from __future__ import annotations

import json
from datetime import UTC, datetime

_next_decision_id = 0

def _gen_decision_id():
    global _next_decision_id
    _next_decision_id += 1
    return _next_decision_id

def record_decision(store, candidate, decision, reason=None, config_change=None):
    store.execute("""
        INSERT INTO ratchet_decisions (decision_id, decided_at, candidate_type, candidate_key,
            decision, reason, evidence, config_change)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [_gen_decision_id(), datetime.now(UTC), candidate.candidate_type,
         candidate.candidate_key, decision, reason, json.dumps(candidate.evidence),
         json.dumps(config_change) if config_change else None])
