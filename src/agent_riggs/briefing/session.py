"""Generate session briefings from cross-session data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from agent_riggs.config import RiggsConfig
from agent_riggs.ratchet.candidates import find_nudge_candidates, nudge_heed_summary
from agent_riggs.store import Store


@dataclass
class SessionBriefing:
    trust_baseline: float | None
    turn_count: int = 0
    session_count: int = 0
    last_activity: str | None = None
    last_session: dict[str, Any] | None = None
    activity: list[str] = field(default_factory=list)
    nudge_lines: list[str] = field(default_factory=list)
    known_issues: list[str] = field(default_factory=list)
    candidate_lines: list[str] = field(default_factory=list)
    active_candidates: int = 0

    def format(self):
        lines = []
        if self.trust_baseline is not None:
            lines.append(
                f"Trust baseline: {self.trust_baseline:.2f} "
                f"({self.turn_count} turns across {self.session_count} sessions)"
            )
        else:
            lines.append("Trust baseline: no data (run `agent-riggs ingest`)")
        if self.last_activity:
            lines.append(f"Last activity: {self.last_activity}")
        if self.last_session:
            s = self.last_session
            lines.append(
                f"Last session: {s['session_id'][:8]} — {s['total_turns']} turns, "
                f"{s['sources']}"
            )
        if self.activity:
            lines.append("\nRecent activity:")
            lines.extend(f"  {a}" for a in self.activity)
        if self.nudge_lines:
            lines.append("\nNudge experiments (kibitzer A/B):")
            lines.extend(f"  {n}" for n in self.nudge_lines)
        if self.known_issues:
            lines.append("\nKnown issues:")
            lines.extend(f"  - {issue}" for issue in self.known_issues)
        if self.candidate_lines:
            lines.append(f"\nRatchet candidates ({self.active_candidates}):")
            lines.extend(f"  {c}" for c in self.candidate_lines)
        elif self.trust_baseline is not None:
            lines.append("\nRatchet candidates: none (no measured heed evidence qualifies)")
        return "\n".join(lines)


def generate_briefing(store: Store, project: str, config: RiggsConfig) -> SessionBriefing:
    trust_row = store.execute(
        """SELECT trust_15, count(*) OVER (), CAST(max(timestamp) OVER () AS VARCHAR)
           FROM turns WHERE project = ? ORDER BY timestamp DESC LIMIT 1""",
        [project],
    ).fetchone()
    if trust_row is None:
        return SessionBriefing(trust_baseline=None)

    session_count = store.execute(
        "SELECT count(DISTINCT session_id) FROM turns WHERE project = ?", [project]
    ).fetchone()[0]

    cutoff = datetime.now(UTC) - timedelta(days=config.briefing.lookback_days)

    briefing = SessionBriefing(
        trust_baseline=trust_row[0],
        turn_count=trust_row[1],
        session_count=session_count,
        last_activity=trust_row[2],
        last_session=_last_session(store, project),
        activity=_activity_lines(store, project, cutoff, config),
        nudge_lines=_nudge_lines(store, config),
        known_issues=_known_issues(store, project),
    )

    candidates = find_nudge_candidates(store, project, config.ratchet)
    briefing.active_candidates = len(candidates)
    briefing.candidate_lines = [f"[{c.candidate_type}] {c.candidate_key}" for c in candidates]
    return briefing


def _last_session(store: Store, project: str) -> dict[str, Any] | None:
    row = store.execute(
        """
        SELECT session_id, count(*) AS total_turns,
               string_agg(DISTINCT source, ', ' ORDER BY source) AS sources
        FROM turns WHERE project = ?
        GROUP BY session_id
        ORDER BY max(timestamp) DESC LIMIT 1
        """,
        [project],
    ).fetchone()
    if row is None:
        return None
    return {"session_id": row[0], "total_turns": row[1], "sources": row[2] or "unknown"}


def _activity_lines(store: Store, project: str, cutoff: datetime, config: RiggsConfig) -> list:
    lines: list[str] = []
    days = config.briefing.lookback_days

    # blq: build/test runs and outcomes
    row = store.execute(
        """
        SELECT count(*),
               count(*) FILTER (WHERE NOT tool_success),
               max(CASE WHEN NOT tool_success
                   THEN json_extract_string(metadata, '$.cmd') END)
        FROM turns
        WHERE project = ? AND source = 'blq' AND timestamp > ?
        """,
        [project, cutoff],
    ).fetchone()
    if row and row[0]:
        runs, failed, last_fail = row
        line = f"builds/tests (blq): {runs} runs, {failed} failed"
        if last_fail:
            line += f" — last failure: {last_fail[:60]}"
        lines.append(line)

    # jetsam: git workflow plans by verb
    rows = store.execute(
        """
        SELECT json_extract_string(metadata, '$.verb') AS verb, count(*)
        FROM turns
        WHERE project = ? AND source = 'jetsam' AND timestamp > ?
        GROUP BY verb ORDER BY count(*) DESC
        """,
        [project, cutoff],
    ).fetchall()
    if rows:
        total = sum(r[1] for r in rows)
        verbs = ", ".join(f"{n} {v}" for v, n in rows)
        lines.append(f"git workflow (jetsam): {total} plans — {verbs}")

    # kibitzer: intercepted bypasses by suggested plugin
    rows = store.execute(
        """
        SELECT coalesce(json_extract_string(metadata, '$.plugin'), 'other') AS plugin, count(*)
        FROM turns
        WHERE project = ? AND source = 'kibitzer' AND event_category = 'suboptimal'
        GROUP BY plugin ORDER BY count(*) DESC
        """,
        [project],
    ).fetchall()
    if rows:
        total = sum(r[1] for r in rows)
        top = ", ".join(f"{p} {n}" for p, n in rows[:4])
        lines.append(f"bypasses intercepted (kibitzer): {total} — {top}")

    # fledgling: session tool usage
    row = store.execute(
        """
        SELECT count(*), count(DISTINCT session_id),
               count(*) FILTER (WHERE event_category = 'suboptimal')
        FROM turns
        WHERE project = ? AND source = 'fledgling' AND timestamp > ?
        """,
        [project, cutoff],
    ).fetchone()
    if row and row[0]:
        calls, sessions, subopt = row
        top_rows = store.execute(
            """
            SELECT tool_name, count(*) FROM turns
            WHERE project = ? AND source = 'fledgling' AND timestamp > ?
              AND tool_name IS NOT NULL
            GROUP BY tool_name ORDER BY count(*) DESC LIMIT ?
            """,
            [project, cutoff, config.briefing.top_tools],
        ).fetchall()
        top = ", ".join(f"{t} {n}" for t, n in top_rows)
        line = f"sessions (fledgling, {days}d): {calls} tool calls in {sessions} sessions"
        if top:
            line += f" — top: {top}"
        if subopt:
            line += f"; {subopt} replaceable bash calls"
        lines.append(line)

    return lines


def _nudge_lines(store: Store, config: RiggsConfig) -> list[str]:
    lines = []
    for s in nudge_heed_summary(store):
        promotable = (
            s["nudges"] >= config.ratchet.min_nudge_trials
            and s["heed_rate"] >= config.ratchet.min_heed_rate
            and s["lift"] >= config.ratchet.min_heed_lift
        )
        if s["nudges"] < config.ratchet.min_nudge_trials:
            verdict = f"insufficient trials (n={s['nudges']})"
        elif promotable:
            verdict = "PROMOTABLE"
        else:
            verdict = "not promotable"
        lines.append(
            f"{s['plugin']}: {s['nudges']} nudges, {s['heed_rate']:.0%} heeded "
            f"(control {s['control_heed_rate']:.0%}, lift {s['lift']:+.0%}) — {verdict}"
        )
    return lines


def _known_issues(store: Store, project: str) -> list[str]:
    failure_rows = store.execute(
        """SELECT failure_category, count(*) AS cnt FROM failure_stream
           WHERE project = ? GROUP BY failure_category
           HAVING count(*) >= 3 ORDER BY cnt DESC LIMIT 5""",
        [project],
    ).fetchall()
    return [f"{r[0]} ({r[1]} occurrences)" for r in failure_rows]
