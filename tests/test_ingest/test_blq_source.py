from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb

from agent_riggs.ingest.sources.blq import BlqSource
from agent_riggs.trust.events import EventCategory


def _create_blq_db(project: Path) -> Path:
    bird_dir = project / ".bird"
    bird_dir.mkdir(exist_ok=True)
    db_path = bird_dir / "blq.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE invocations (
            id UUID PRIMARY KEY DEFAULT uuid(),
            session_id VARCHAR,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cmd VARCHAR NOT NULL,
            executable VARCHAR,
            exit_code INTEGER NOT NULL,
            duration_ms BIGINT,
            source_name VARCHAR,
            date DATE DEFAULT CURRENT_DATE
        )
    """)
    conn.close()
    return db_path


def _insert_invocation(project, cmd, exit_code, ts=None, source_name=None):
    db_path = project / ".bird" / "blq.duckdb"
    conn = duckdb.connect(str(db_path))
    ts = ts or datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO invocations (id, session_id, timestamp, cmd, exit_code, source_name) VALUES (?, ?, ?, ?, ?, ?)",
        [str(uuid4()), "sess-1", ts, cmd, exit_code, source_name],
    )
    conn.close()


def test_discover_when_present(tmp_project):
    _create_blq_db(tmp_project)
    assert BlqSource().discover(tmp_project) is True


def test_discover_when_absent(tmp_project):
    assert BlqSource().discover(tmp_project) is False


def test_successful_command(tmp_project):
    _create_blq_db(tmp_project)
    _insert_invocation(tmp_project, "pytest tests/ -x", 0, source_name="test")
    events = BlqSource().read_events(tmp_project, since=None)
    assert len(events) == 1
    assert events[0].event_category == EventCategory.SUCCESS
    assert events[0].tool_success is True


def test_failed_command(tmp_project):
    _create_blq_db(tmp_project)
    _insert_invocation(tmp_project, "pytest tests/ -x", 1, source_name="test")
    events = BlqSource().read_events(tmp_project, since=None)
    assert len(events) == 1
    assert events[0].event_category == EventCategory.FAILURE
    assert events[0].tool_success is False


def test_respects_since(tmp_project):
    _create_blq_db(tmp_project)
    _insert_invocation(tmp_project, "pytest", 0, ts=datetime(2026, 3, 30, tzinfo=timezone.utc))
    _insert_invocation(tmp_project, "pytest", 1, ts=datetime(2026, 3, 31, tzinfo=timezone.utc))
    since = datetime(2026, 3, 31, tzinfo=timezone.utc)
    events = BlqSource().read_events(tmp_project, since=since)
    assert len(events) == 1
    assert events[0].event_category == EventCategory.FAILURE
