"""The gate must actually be invoked on enforcement paths (not just defined).

On the vulnerable code the transition logic was dead code referenced only by
tests, and nothing consumed trust before a capability-expanding action.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from click.testing import CliRunner

from agent_riggs.assembly import assemble
from agent_riggs.cli import main


def _seed_tool_candidate(project: Path) -> None:
    """Seed turns rows that produce a tool_promotion (capability-expanding) candidate."""
    service = assemble(project)
    base = datetime.now(UTC) - timedelta(days=1)
    for i in range(6):
        service.store.execute(
            """INSERT INTO turns (turn_id, session_id, project, turn_number, timestamp,
                   tool_name, tool_success, mode, trust_score, trust_1, trust_5, trust_15,
                   event_category, metadata)
               VALUES (?, ?, ?, ?, ?, 'Bash', true, 'implement', 1.0, 0.9, 0.9, 0.9,
                       'success', ?)""",
            [
                50000 + i,
                f"sess-{i % 3}",
                project.name,
                i,
                base + timedelta(minutes=i),
                json.dumps({"command": "pytest tests/"}),
            ],
        )
    service.store.close()


def _accrue_observed_trust(project: Path, n: int = 40) -> None:
    bird = project / ".bird"
    bird.mkdir(exist_ok=True)
    conn = duckdb.connect(str(bird / "blq.duckdb"))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS invocations (
            id INTEGER, session_id VARCHAR, timestamp TIMESTAMP, cmd VARCHAR,
            executable VARCHAR, exit_code INTEGER, duration_ms INTEGER, source_name VARCHAR
        )"""
    )
    base = datetime(2026, 6, 2, 9, 0)
    for i in range(n):
        conn.execute(
            "INSERT INTO invocations VALUES (?, ?, ?, ?, ?, 0, 100, 'test')",
            [i + 1, "sess-blq", base + timedelta(minutes=i), "pytest", "pytest"],
        )
    conn.close()

    from agent_riggs.config import load_config
    from agent_riggs.ingest.pipeline import ingest
    from agent_riggs.ingest.sources.blq import BlqSource
    from agent_riggs.plugins.trust import TRUST_DDL
    from agent_riggs.store import Store

    config = load_config(project)
    with Store(project / ".riggs" / "store.duckdb") as store:
        store.ensure_schema(TRUST_DDL)
        ingest(store=store, project_root=project, sources=[BlqSource()], trust_config=config.trust)


def test_promote_tool_candidate_denied_without_verified_trust(tmp_project: Path) -> None:
    _seed_tool_candidate(tmp_project)
    service = assemble(tmp_project)
    try:
        ratchet = service.plugin("ratchet")
        candidates = ratchet.candidates()
        keys = [c.candidate_key for c in candidates if c.candidate_type == "tool_promotion"]
        assert keys, "expected a tool_promotion candidate"

        with pytest.raises(PermissionError):
            ratchet.promote(keys[0])

        row = service.store.execute("SELECT count(*) FROM ratchet_decisions").fetchone()
        assert row == (0,), "denied promotion must not be recorded"
    finally:
        service.store.close()


def test_promote_tool_candidate_allowed_with_verified_trust(tmp_project: Path) -> None:
    _accrue_observed_trust(tmp_project)
    _seed_tool_candidate(tmp_project)
    service = assemble(tmp_project)
    try:
        ratchet = service.plugin("ratchet")
        keys = [
            c.candidate_key for c in ratchet.candidates() if c.candidate_type == "tool_promotion"
        ]
        assert keys
        ratchet.promote(keys[0], reason="verified trust")
        row = service.store.execute("SELECT count(*) FROM ratchet_decisions").fetchone()
        assert row == (1,)
    finally:
        service.store.close()


def test_cli_gate_denies_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["gate"])
    assert result.exit_code == 2
    assert "deny" in result.output.lower()


def test_cli_gate_allows_after_accrual(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])
    _accrue_observed_trust(tmp_path)
    result = runner.invoke(main, ["gate"])
    assert result.exit_code == 0
    assert "allow" in result.output.lower()


def test_ingest_publishes_recommendation_to_kibitzer_state(tmp_project: Path) -> None:
    """README's documented loop: recommendations land in .kibitzer/state.json."""
    kib = tmp_project / ".kibitzer"
    kib.mkdir()
    (kib / "state.json").write_text(json.dumps({"mode": "implement", "session_id": "s1"}))
    with (kib / "intercept.log").open("w") as f:
        for i in range(5):
            f.write(
                json.dumps(
                    {
                        "timestamp": f"2026-06-01T10:0{i}:00Z",
                        "tool": "Edit",
                        "success": False,
                    }
                )
                + "\n"
            )

    service = assemble(tmp_project)
    try:
        service.plugin("ingest").run()
    finally:
        service.store.close()

    state = json.loads((kib / "state.json").read_text())
    assert "riggs" in state, "ingest must publish trust info for kibitzer"
    riggs = state["riggs"]
    assert riggs["gate"]["allowed"] is False
    assert riggs["recommendation"] is not None
    assert "tighten" in riggs["recommendation"]["action"]
