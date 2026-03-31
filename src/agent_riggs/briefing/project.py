"""Project-level health assessment."""
from __future__ import annotations

from typing import Any

from agent_riggs.store import Store


def project_health(store: Store, project: str) -> dict[str, Any]:
    row = store.execute(
        """SELECT count(*), coalesce(avg(trust_end), 1.0), coalesce(avg(failure_rate), 0.0)
           FROM session_summaries WHERE project = ?""",
        [project],
    ).fetchone()
    return {
        "total_sessions": row[0],
        "avg_trust": row[1],
        "avg_failure_rate": row[2],
        "healthy": row[1] >= 0.7 and row[2] <= 0.3,
    }
