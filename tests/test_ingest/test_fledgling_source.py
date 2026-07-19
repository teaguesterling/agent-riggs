from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from agent_riggs.ingest.sources.fledgling import FledglingSource
from agent_riggs.trust.events import EventCategory


def _create_claude_logs(tmp_path: Path, project_cwd: str, records: list[dict]) -> Path:
    """Create a fake ~/.claude/projects/test-project/ with JSONL."""
    project_dir = tmp_path / ".claude" / "projects" / "test-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = project_dir / "conversations.jsonl"
    with jsonl_path.open("a") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return tmp_path


def _make_assistant_record(
    session_id: str,
    tool_name: str,
    tool_input: dict,
    ts: str = "2026-03-31T10:00:00Z",
    cwd: str = "/tmp/my-project",
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    return {
        "uuid": "test-uuid",
        "sessionId": session_id,
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "tu_001", "name": tool_name, "input": tool_input},
            ],
            "model": model,
        },
        "timestamp": ts,
        "cwd": cwd,
    }


def test_discover_when_absent(tmp_project):
    with patch("agent_riggs.ingest.sources.fledgling.Path.home", return_value=tmp_project):
        assert FledglingSource().discover(tmp_project) is False


def test_discover_when_present(tmp_project):
    fake_home = tmp_project / "home"
    _create_claude_logs(
        fake_home,
        "/tmp/my-project",
        [
            _make_assistant_record("s1", "Read", {"file_path": "x.py"}),
        ],
    )
    with patch("agent_riggs.ingest.sources.fledgling.Path.home", return_value=fake_home):
        assert FledglingSource().discover(tmp_project) is True


def test_read_tool_use(tmp_project):
    fake_home = tmp_project / "home"
    project_path = tmp_project / "my-project"
    project_path.mkdir()
    _create_claude_logs(
        fake_home,
        str(project_path),
        [
            _make_assistant_record("s1", "Read", {"file_path": "x.py"}, cwd=str(project_path)),
        ],
    )
    with patch("agent_riggs.ingest.sources.fledgling.Path.home", return_value=fake_home):
        batch = FledglingSource().read_events(project_path, cursor=None)
        assert len(batch.events) == 1
        assert batch.events[0].tool_name == "Read"
        assert batch.events[0].event_category == EventCategory.SUCCESS


def test_bash_with_alternative_is_suboptimal(tmp_project):
    fake_home = tmp_project / "home"
    project_path = tmp_project / "my-project"
    project_path.mkdir()
    _create_claude_logs(
        fake_home,
        str(project_path),
        [
            _make_assistant_record(
                "s1", "Bash", {"command": "grep -rn 'def foo' src/"}, cwd=str(project_path)
            ),
        ],
    )
    with patch("agent_riggs.ingest.sources.fledgling.Path.home", return_value=fake_home):
        batch = FledglingSource().read_events(project_path, cursor=None)
        assert len(batch.events) == 1
        assert batch.events[0].event_category == EventCategory.SUBOPTIMAL


def test_cursor_makes_reads_incremental(tmp_project):
    fake_home = tmp_project / "home"
    project_path = tmp_project / "my-project"
    project_path.mkdir()
    _create_claude_logs(
        fake_home,
        str(project_path),
        [
            _make_assistant_record(
                "s1", "Read", {}, ts="2026-03-30T10:00:00Z", cwd=str(project_path)
            ),
            _make_assistant_record(
                "s1", "Edit", {}, ts="2026-03-31T10:00:00Z", cwd=str(project_path)
            ),
        ],
    )
    with patch("agent_riggs.ingest.sources.fledgling.Path.home", return_value=fake_home):
        source = FledglingSource()
        first = source.read_events(project_path, cursor=None)
        assert len(first.events) == 2

        # Nothing new: cursor tracks per-file line offsets.
        second = source.read_events(project_path, first.cursor)
        assert second.events == []

        # A session appends a new record: only it is read.
        _create_claude_logs(
            fake_home,
            str(project_path),
            [
                _make_assistant_record(
                    "s1", "Write", {}, ts="2026-04-01T10:00:00Z", cwd=str(project_path)
                ),
            ],
        )
        third = source.read_events(project_path, second.cursor)
        assert len(third.events) == 1
        assert third.events[0].tool_name == "Write"
