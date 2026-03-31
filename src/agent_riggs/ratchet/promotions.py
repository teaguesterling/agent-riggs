"""Apply and record ratchet promotion decisions."""

from __future__ import annotations

import json
from datetime import UTC, datetime


def record_decision(store, candidate, decision, reason=None, config_change=None):
    row = store.execute(
        "SELECT coalesce(max(decision_id), 0) FROM ratchet_decisions"
    ).fetchone()
    next_id = row[0] + 1

    store.execute(
        """
        INSERT INTO ratchet_decisions (decision_id, decided_at, candidate_type, candidate_key,
            decision, reason, evidence, config_change)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            next_id,
            datetime.now(UTC),
            candidate.candidate_type,
            candidate.candidate_key,
            decision,
            reason,
            json.dumps(candidate.evidence),
            json.dumps(config_change) if config_change else None,
        ],
    )
