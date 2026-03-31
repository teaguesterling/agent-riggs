from __future__ import annotations

from datetime import UTC, datetime

from agent_riggs.metrics.compute import RatchetMetrics, compute_metrics
from agent_riggs.store import Store


def _get_all_ddl():
    from agent_riggs.plugins.ratchet import RATCHET_DDL
    from agent_riggs.plugins.trust import TRUST_DDL
    return TRUST_DDL + RATCHET_DDL

def _seed_session_data(store, project):
    for i in range(20):
        session = f"sess-{i % 3}"
        store.execute("""INSERT INTO turns (turn_id, session_id, project, turn_number, timestamp,
            tool_name, tool_success, mode, trust_score, trust_1, trust_5, trust_15, event_category, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [i + 30000, session, project, i + 1,
             datetime(2026, 3, 29, 10, i, 0, tzinfo=UTC),
             "Read" if i % 3 != 0 else "Bash", True, "implement",
             1.0 if i % 3 != 0 else 0.7, 0.9, 0.85, 0.87,
             "success" if i % 3 != 0 else "suboptimal", "{}"])
    for i in range(3):
        store.execute("""INSERT INTO session_summaries (session_id, project, total_turns, total_failures,
            failure_rate, trust_start, trust_end, trust_delta, modes_used, mode_switches,
            computation_channel_fraction, structured_tool_fraction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [f"sess-{i}", project, 7, 1, 0.14, 0.85, 0.90, 0.05,
             ["implement", "debug"], 1, 0.35, 0.65])

def test_compute_metrics(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(_get_all_ddl())
        project = tmp_project.name
        _seed_session_data(store, project)
        metrics = compute_metrics(store, project, period_days=30)
        assert isinstance(metrics, RatchetMetrics)
        assert metrics.total_sessions == 3
        assert metrics.total_turns == 20
        assert 0 <= metrics.structured_tool_fraction <= 1

def test_compute_metrics_empty_store(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(_get_all_ddl())
        project = tmp_project.name
        metrics = compute_metrics(store, project, period_days=30)
        assert metrics.total_sessions == 0
        assert metrics.total_turns == 0
