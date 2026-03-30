"""Generate session briefings from cross-session data."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from agent_riggs.config import RiggsConfig
from agent_riggs.store import Store


@dataclass
class SessionBriefing:
    trust_baseline: float | None
    last_session: dict[str, Any] | None
    known_issues: list[str]
    active_candidates: int

    def format(self):
        lines = []
        if self.trust_baseline is not None:
            lines.append(f"Trust baseline: {self.trust_baseline:.2f}")
        else:
            lines.append("Trust baseline: no data")
        if self.last_session:
            s = self.last_session
            lines.append(f"Last session: {s['session_id']}, {s['total_turns']} turns, trust {s['trust_end']:.2f}")
        else:
            lines.append("Last session: none")
        if self.known_issues:
            lines.append("\nKnown issues:")
            for issue in self.known_issues:
                lines.append(f"  - {issue}")
        if self.active_candidates > 0:
            lines.append(f"\nActive ratchet candidates: {self.active_candidates}")
        return "\n".join(lines)


def generate_briefing(store: Store, project: str, config: RiggsConfig) -> SessionBriefing:
    trust_row = store.execute(
        "SELECT trust_15 FROM turns WHERE project = ? ORDER BY timestamp DESC LIMIT 1",
        [project],
    ).fetchone()
    trust_baseline = trust_row[0] if trust_row else None

    session_row = store.execute(
        """SELECT session_id, total_turns, total_failures, trust_end, CAST(ended_at AS VARCHAR)
           FROM session_summaries WHERE project = ? ORDER BY ended_at DESC LIMIT 1""",
        [project],
    ).fetchone()
    last_session = None
    if session_row:
        last_session = {
            "session_id": session_row[0],
            "total_turns": session_row[1],
            "total_failures": session_row[2],
            "trust_end": session_row[3],
            "ended_at": session_row[4],
        }

    failure_rows = store.execute(
        """SELECT failure_category, count(*) AS cnt FROM failure_stream
           WHERE project = ? GROUP BY failure_category HAVING count(*) >= 3 ORDER BY cnt DESC LIMIT 5""",
        [project],
    ).fetchall()
    known_issues = [f"{r[0]} ({r[1]} occurrences)" for r in failure_rows]

    candidate_row = store.execute(
        """SELECT count(DISTINCT failure_category || coalesce(tool_name, '') || coalesce(mode, ''))
           FROM failure_stream WHERE project = ? GROUP BY project HAVING count(*) >= ?""",
        [project, config.ratchet.min_frequency],
    ).fetchone()
    active_candidates = candidate_row[0] if candidate_row else 0

    return SessionBriefing(
        trust_baseline=trust_baseline,
        last_session=last_session,
        known_issues=known_issues,
        active_candidates=active_candidates,
    )
