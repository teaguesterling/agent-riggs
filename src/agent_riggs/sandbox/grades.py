"""Read blq sandbox grades and aggregate across sessions. Stub — requires blq."""

from __future__ import annotations

from typing import Any

from agent_riggs.store import Store


def get_grades(store: Store, project: str) -> list[dict[str, Any]]:
    rows = store.execute(
        """SELECT command, current_grade_w, current_effects_ceiling,
           total_runs, memory_p95, memory_max FROM sandbox_profiles
           WHERE project = ? ORDER BY command""",
        [project],
    ).fetchall()
    return [
        {
            "command": r[0],
            "grade": r[1],
            "effects_ceiling": r[2],
            "runs": r[3],
            "memory_p95": r[4],
            "memory_max": r[5],
        }
        for r in rows
    ]
