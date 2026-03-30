from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from agent_riggs.cli import main


def test_init_creates_riggs_dir(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / ".riggs").is_dir()
    assert (tmp_path / ".riggs" / "config.toml").exists()
    assert (tmp_path / ".riggs" / "store.duckdb").exists()


def test_init_idempotent(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
