"""Shared fixtures for agent_riggs tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_state_dir(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point the out-of-tree trust state directory at a per-test temp dir.

    Trust state (ledger + key) lives outside the project tree; tests must
    never read or write the developer's real state directory.
    """
    state_dir = tmp_path_factory.mktemp("riggs-state")
    monkeypatch.setenv("AGENT_RIGGS_STATE_DIR", str(state_dir))
    return state_dir


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A temporary project directory with .riggs/ created."""
    riggs_dir = tmp_path / ".riggs"
    riggs_dir.mkdir()
    return tmp_path
