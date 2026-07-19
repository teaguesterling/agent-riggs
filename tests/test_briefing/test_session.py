from __future__ import annotations

import json
from datetime import UTC, datetime

from agent_riggs.briefing.session import SessionBriefing, generate_briefing
from agent_riggs.config import load_config
from agent_riggs.store import Store

_turn_id_seq = 0
_trial_id_seq = 0


def _get_all_ddl():
    from agent_riggs.plugins.ingest import INGEST_DDL
    from agent_riggs.plugins.ratchet import RATCHET_DDL
    from agent_riggs.plugins.trust import TRUST_DDL

    return TRUST_DDL + RATCHET_DDL + INGEST_DDL


def _seed_turn(
    store,
    project,
    source,
    tool_name="Read",
    tool_success=True,
    category="success",
    metadata=None,
    session_id="sess-1",
    ts=None,
):
    global _turn_id_seq
    _turn_id_seq += 1
    store.execute(
        """INSERT INTO turns (turn_id, session_id, project, turn_number,
           timestamp, tool_name, tool_success, mode, trust_score, trust_1,
           trust_5, trust_15, event_category, metadata, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            _turn_id_seq + 50000,
            session_id,
            project,
            _turn_id_seq,
            ts or datetime.now(UTC),
            tool_name,
            tool_success,
            None,
            1.0,
            0.91,
            0.88,
            0.87,
            category,
            json.dumps(metadata or {}),
            source,
        ],
    )


def _seed_trial(store, plugin, arm, heed):
    global _trial_id_seq
    _trial_id_seq += 1
    store.execute(
        """INSERT INTO nudge_trials (trial_id, plugin, arm, heed, turns_to_heed,
            session_id, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [_trial_id_seq + 70000, plugin, arm, heed, None, "sess-1", datetime.now(UTC)],
    )


def test_briefing_no_data(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = load_config(tmp_project)
    with Store(db_path) as store:
        store.ensure_schema(_get_all_ddl())
        briefing = generate_briefing(store, tmp_project.name, config)
        assert isinstance(briefing, SessionBriefing)
        assert briefing.trust_baseline is None
        assert "no data" in briefing.format()


def test_briefing_with_data(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = load_config(tmp_project)
    with Store(db_path) as store:
        store.ensure_schema(_get_all_ddl())
        _seed_turn(store, tmp_project.name, "fledgling", tool_name="Read")
        briefing = generate_briefing(store, tmp_project.name, config)
        assert briefing.trust_baseline == 0.87
        assert briefing.turn_count == 1
        assert briefing.last_session is not None
        assert briefing.last_session["session_id"] == "sess-1"


def test_briefing_summarizes_source_activity(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = load_config(tmp_project)
    with Store(db_path) as store:
        store.ensure_schema(_get_all_ddl())
        project = tmp_project.name

        # blq: one pass, one fail
        _seed_turn(store, project, "blq", tool_name="blq.test", tool_success=True)
        _seed_turn(
            store,
            project,
            "blq",
            tool_name="blq.test",
            tool_success=False,
            category="failure",
            metadata={"cmd": "pytest tests/", "exit_code": 1},
        )
        # jetsam: two plans
        _seed_turn(store, project, "jetsam", tool_name="jetsam.sync", metadata={"verb": "sync"})
        _seed_turn(store, project, "jetsam", tool_name="jetsam.save", metadata={"verb": "save"})
        # kibitzer: an intercepted bypass
        _seed_turn(
            store,
            project,
            "kibitzer",
            tool_name="Bash",
            category="suboptimal",
            metadata={"bash_command": "git push", "suggested_tool": "jetsam sync",
                      "plugin": "jetsam"},
        )
        # fledgling: session tool calls
        _seed_turn(store, project, "fledgling", tool_name="Read")
        _seed_turn(store, project, "fledgling", tool_name="Edit")

        text = generate_briefing(store, project, config).format()

        assert "builds/tests (blq): 2 runs, 1 failed" in text
        assert "pytest tests/" in text
        assert "git workflow (jetsam): 2 plans" in text
        assert "bypasses intercepted (kibitzer): 1" in text
        assert "sessions (fledgling" in text


def test_briefing_shows_nudge_evidence_and_gate(tmp_project):
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = load_config(tmp_project)
    with Store(db_path) as store:
        store.ensure_schema(_get_all_ddl())
        project = tmp_project.name
        _seed_turn(store, project, "kibitzer")

        # jetsam: frequent but never heeded -> shown as evidence, NOT a candidate
        for _ in range(8):
            _seed_trial(store, "jetsam", "nudge", heed=False)
        _seed_trial(store, "jetsam", "control", heed=False)

        briefing = generate_briefing(store, project, config)
        text = briefing.format()

        assert "jetsam: 8 nudges, 0% heeded" in text
        assert "not promotable" in text
        assert briefing.active_candidates == 0
        assert "Ratchet candidates: none" in text
