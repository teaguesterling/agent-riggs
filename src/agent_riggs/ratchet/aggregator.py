"""Cross-session failure stream aggregation."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta


def failure_summary(store, project, days=30):
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = store.execute("""
        SELECT failure_category, count(*) AS count,
               count(DISTINCT session_id) AS sessions_affected,
               round(avg(trust_at_failure), 2) AS avg_trust
        FROM failure_stream WHERE project = ?
          AND occurred_at > ?
        GROUP BY failure_category ORDER BY count DESC""", [project, cutoff]).fetchall()
    return [{"category": r[0], "count": r[1], "sessions_affected": r[2], "avg_trust": r[3]} for r in rows]
