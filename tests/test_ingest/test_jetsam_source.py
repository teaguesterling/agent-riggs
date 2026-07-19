from __future__ import annotations

import json
from pathlib import Path

from agent_riggs.ingest.sources.jetsam import JetsamSource
from agent_riggs.trust.events import EventCategory


def _write_plan(project: Path, plan_id: str, verb: str = "sync", created_at: float = 1.0) -> None:
    plans_dir = project / ".jetsam" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / f"{plan_id}.json").write_text(
        json.dumps(
            {
                "plan_id": plan_id,
                "verb": verb,
                "steps": [{"action": "fetch", "remote": "origin"}, {"action": "merge"}],
                "warnings": [],
                "repo_root": str(project),
                "created_at": created_at,
            }
        )
    )


def test_discover_when_plans_present(tmp_project: Path) -> None:
    _write_plan(tmp_project, "p_1")
    assert JetsamSource().discover(tmp_project) is True


def test_discover_when_absent(tmp_project: Path) -> None:
    assert JetsamSource().discover(tmp_project) is False


def test_read_plans_as_events(tmp_project: Path) -> None:
    _write_plan(tmp_project, "p_1", verb="sync", created_at=1000.0)
    _write_plan(tmp_project, "p_2", verb="save", created_at=2000.0)

    batch = JetsamSource().read_events(tmp_project, cursor=None)
    assert len(batch.events) == 2
    assert batch.events[0].tool_name == "jetsam.sync"
    assert batch.events[1].tool_name == "jetsam.save"
    assert all(e.event_category == EventCategory.SUCCESS for e in batch.events)
    assert batch.events[0].metadata["steps"] == ["fetch", "merge"]


def test_cursor_skips_seen_plans(tmp_project: Path) -> None:
    _write_plan(tmp_project, "p_1", created_at=1000.0)
    source = JetsamSource()

    first = source.read_events(tmp_project, cursor=None)
    assert len(first.events) == 1
    assert "p_1" in first.cursor["seen_plans"]

    second = source.read_events(tmp_project, first.cursor)
    assert second.events == []

    _write_plan(tmp_project, "p_2", verb="ship", created_at=2000.0)
    third = source.read_events(tmp_project, second.cursor)
    assert len(third.events) == 1
    assert third.events[0].tool_name == "jetsam.ship"
    assert set(third.cursor["seen_plans"]) == {"p_1", "p_2"}


def test_malformed_plan_is_skipped(tmp_project: Path) -> None:
    plans_dir = tmp_project / ".jetsam" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "bad.json").write_text("{not json")
    _write_plan(tmp_project, "p_ok")

    batch = JetsamSource().read_events(tmp_project, cursor=None)
    assert len(batch.events) == 1
    assert batch.events[0].metadata["plan_id"] == "p_ok"
