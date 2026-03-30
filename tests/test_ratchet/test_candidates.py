from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.config import RatchetConfig
from agent_riggs.ratchet.candidates import Candidate, find_constraint_candidates
from agent_riggs.ratchet.aggregator import failure_summary
from agent_riggs.store import Store
from agent_riggs.plugins.trust import TRUST_DDL


_failure_id_seq = 0


def _seed_failures(store, project, count, category="edit_failure", tool="Edit",
                   mode="implement", session_count=5):
    global _failure_id_seq
    for i in range(count):
        session = f"sess-{i % session_count}"
        _failure_id_seq += 1
        store.execute(
            """INSERT INTO failure_stream (failure_id, turn_id, session_id, project, occurred_at,
                failure_category, tool_name, mode, trust_at_failure, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [_failure_id_seq + 20000, _failure_id_seq + 10000, session, project,
             datetime(2026, 3, 29, 10, 0, 0, tzinfo=timezone.utc),
             category, tool, mode, 0.5, "{}"])


def test_find_constraint_candidates(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = RatchetConfig(min_frequency=3, min_sessions=2)
    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL)
        project = tmp_project.name
        _seed_failures(store, project, count=10, session_count=5)
        candidates = find_constraint_candidates(store, project, config)
        assert len(candidates) >= 1
        assert candidates[0].candidate_type == "constraint_promotion"
        assert candidates[0].evidence["occurrences"] == 10


def test_no_candidates_below_threshold(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = RatchetConfig(min_frequency=20, min_sessions=10)
    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL)
        project = tmp_project.name
        _seed_failures(store, project, count=5, session_count=2)
        candidates = find_constraint_candidates(store, project, config)
        assert len(candidates) == 0


def test_failure_summary(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL)
        project = tmp_project.name
        _seed_failures(store, project, count=10, category="edit_failure")
        _seed_failures(store, project, count=5, category="path_denial")
        summary = failure_summary(store, project)
        assert len(summary) >= 2
        total = sum(s["count"] for s in summary)
        assert total == 15
