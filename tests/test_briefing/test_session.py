from __future__ import annotations

from datetime import UTC, datetime

from agent_riggs.briefing.session import SessionBriefing, generate_briefing
from agent_riggs.config import load_config
from agent_riggs.store import Store


def _get_all_ddl():
    from agent_riggs.plugins.ratchet import RATCHET_DDL
    from agent_riggs.plugins.trust import TRUST_DDL
    return TRUST_DDL + RATCHET_DDL


def test_briefing_no_data(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = load_config(tmp_project)
    with Store(db_path) as store:
        store.ensure_schema(_get_all_ddl())
        briefing = generate_briefing(store, tmp_project.name, config)
        assert isinstance(briefing, SessionBriefing)
        assert briefing.trust_baseline is None
        assert briefing.last_session is None


def test_briefing_with_data(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = load_config(tmp_project)
    with Store(db_path) as store:
        store.ensure_schema(_get_all_ddl())
        store.execute("""INSERT INTO session_summaries (session_id, project, started_at, ended_at,
            total_turns, total_failures, failure_rate, trust_start, trust_end, trust_delta,
            modes_used, mode_switches, computation_channel_fraction, structured_tool_fraction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ["sess-1", tmp_project.name,
             datetime(2026, 3, 29, 8, 0, tzinfo=UTC),
             datetime(2026, 3, 29, 10, 0, tzinfo=UTC),
             34, 2, 0.06, 0.85, 0.91, 0.06, ["implement"], 0, 0.3, 0.7])
        store.execute("""INSERT INTO turns (turn_id, session_id, project, turn_number, timestamp,
            tool_name, tool_success, mode, trust_score, trust_1, trust_5, trust_15, event_category, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [50000, "sess-1", tmp_project.name, 34,
             datetime(2026, 3, 29, 10, 0, tzinfo=UTC),
             "Read", True, "implement", 1.0, 0.91, 0.88, 0.87, "success", "{}"])
        briefing = generate_briefing(store, tmp_project.name, config)
        assert briefing.trust_baseline == 0.87
        assert briefing.last_session is not None
        assert briefing.last_session["session_id"] == "sess-1"
