from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agent_riggs.config import RatchetConfig
from agent_riggs.plugins.ingest import INGEST_DDL
from agent_riggs.plugins.trust import TRUST_DDL
from agent_riggs.ratchet.aggregator import failure_summary
from agent_riggs.ratchet.candidates import (
    find_constraint_candidates,
    find_nudge_candidates,
    nudge_heed_summary,
)
from agent_riggs.store import Store

_failure_id_seq = 0
_trial_id_seq = 0


def _seed_failures(
    store, project, count, category="edit_failure", tool="Edit", mode="implement", session_count=5
):
    global _failure_id_seq
    for i in range(count):
        session = f"sess-{i % session_count}"
        _failure_id_seq += 1
        store.execute(
            """INSERT INTO failure_stream (failure_id, turn_id, session_id, project, occurred_at,
                failure_category, tool_name, mode, trust_at_failure, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                _failure_id_seq + 20000,
                _failure_id_seq + 10000,
                session,
                project,
                # Relative to now: a fixed date rots out of the lookback window.
                datetime.now(UTC) - timedelta(days=1),
                category,
                tool,
                mode,
                0.5,
                "{}",
            ],
        )


def _seed_trials(store, plugin, arm, count, heeded=0, session_count=5):
    global _trial_id_seq
    for i in range(count):
        _trial_id_seq += 1
        store.execute(
            """INSERT INTO nudge_trials (trial_id, plugin, arm, heed, turns_to_heed,
                session_id, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                _trial_id_seq + 30000,
                plugin,
                arm,
                i < heeded,
                1 if i < heeded else None,
                f"sess-{i % session_count}",
                datetime(2026, 3, 29, 10, 0, 0, tzinfo=UTC),
            ],
        )


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


# --- Nudged tool promotion: gated on measured heed, never raw frequency ---


def test_high_frequency_low_heed_is_not_surfaced(tmp_project):
    """The correlation/causation gate: 30 nudges, none heeded -> no candidate.

    This is the real jetsam pattern: its bypass fires constantly (high
    frequency), but the A/B shows nudging never changes behavior. The old
    frequency-only ratchet would have graduated it; the heed gate must not.
    """
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = RatchetConfig(min_frequency=5, min_sessions=2, min_nudge_trials=5)
    with Store(db_path) as store:
        store.ensure_schema(INGEST_DDL)
        _seed_trials(store, "jetsam", "nudge", count=30, heeded=0)
        _seed_trials(store, "jetsam", "control", count=5, heeded=0)

        summary = nudge_heed_summary(store)
        jetsam = next(s for s in summary if s["plugin"] == "jetsam")
        assert jetsam["trials"] == 35  # plenty of frequency evidence
        assert jetsam["heed_rate"] == 0.0  # but no measured heed

        candidates = find_nudge_candidates(store, tmp_project.name, config)
        assert candidates == []


def test_measured_heed_with_lift_is_surfaced(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = RatchetConfig(min_frequency=5, min_sessions=2, min_nudge_trials=5)
    with Store(db_path) as store:
        store.ensure_schema(INGEST_DDL)
        # 10 nudges, 6 heeded (60%); 8 controls, 1 heeded (12.5%) -> lift +47%
        _seed_trials(store, "squackit", "nudge", count=10, heeded=6)
        _seed_trials(store, "squackit", "control", count=8, heeded=1)

        candidates = find_nudge_candidates(store, tmp_project.name, config)
        assert len(candidates) == 1
        c = candidates[0]
        assert c.candidate_type == "nudged_tool_promotion"
        assert c.candidate_key == "nudge-squackit"
        assert c.evidence["heed_rate"] == 0.6
        assert c.evidence["lift"] > 0.4


def test_heed_without_lift_is_not_surfaced(tmp_project):
    """High heed but equally high control rate: the nudge adds nothing."""
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = RatchetConfig(
        min_frequency=5, min_sessions=2, min_nudge_trials=5, min_heed_lift=0.05
    )
    with Store(db_path) as store:
        store.ensure_schema(INGEST_DDL)
        _seed_trials(store, "blq", "nudge", count=10, heeded=5)
        _seed_trials(store, "blq", "control", count=10, heeded=5)

        candidates = find_nudge_candidates(store, tmp_project.name, config)
        assert candidates == []


def test_insufficient_trials_is_not_surfaced(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = RatchetConfig(min_frequency=2, min_sessions=1, min_nudge_trials=5)
    with Store(db_path) as store:
        store.ensure_schema(INGEST_DDL)
        _seed_trials(store, "blq", "nudge", count=3, heeded=3)  # 100% heed, tiny n

        candidates = find_nudge_candidates(store, tmp_project.name, config)
        assert candidates == []


def test_missing_nudge_trials_table_degrades_gracefully(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = RatchetConfig()
    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL)  # no INGEST_DDL: table absent
        assert nudge_heed_summary(store) == []
        assert find_nudge_candidates(store, tmp_project.name, config) == []
