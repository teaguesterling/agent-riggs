from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_riggs.cli import main


def test_status_no_data(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "trust" in result.output.lower()


def test_status_with_data(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])

    kib_dir = tmp_path / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(
        json.dumps(
            {
                "mode": "implement",
                "session_id": "sess-1",
            }
        )
    )
    with (kib_dir / "intercept.log").open("w") as f:
        f.write(
            json.dumps(
                {
                    "timestamp": "2026-03-29T10:00:00Z",
                    "tool": "Read",
                    "success": True,
                }
            )
            + "\n"
        )

    runner.invoke(main, ["ingest"])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "trust" in result.output.lower()
