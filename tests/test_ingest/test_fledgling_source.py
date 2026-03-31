from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from agent_riggs.ingest.sources.fledgling import FledglingSource
from agent_riggs.trust.events import EventCategory


def _create_claude_logs(tmp_path: Path, project_cwd: str, records: list[dict]) -> Path:
    """Create a fake ~/.claude/projects/test-project/ with JSONL."""
    project_dir = tmp_path / ".claude" / "projects" / "test-project"
    project_dir.mkdir(parents=True)
    jsonl_path = project_dir / "conversations.jsonl"
    with jsonl_path.open("w") as f:
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
        events = FledglingSource().read_events(project_path, since=None)
        assert len(events) == 1
        assert events[0].tool_name == "Read"
        assert events[0].event_category == EventCategory.SUCCESS


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
        events = FledglingSource().read_events(project_path, since=None)
        assert len(events) == 1
        assert events[0].event_category == EventCategory.SUBOPTIMAL


def test_respects_since(tmp_project):
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
                "s1", "Read", {}, ts="2026-03-31T10:00:00Z", cwd=str(project_path)
            ),
        ],
    )
    with patch("agent_riggs.ingest.sources.fledgling.Path.home", return_value=fake_home):
        since = datetime(2026, 3, 31, tzinfo=UTC)
        events = FledglingSource().read_events(project_path, since=since)
        assert len(events) == 1
