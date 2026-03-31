"""Shared fixtures for agent_riggs tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A temporary project directory with .riggs/ created."""
    riggs_dir = tmp_path / ".riggs"
    riggs_dir.mkdir()
    return tmp_path
