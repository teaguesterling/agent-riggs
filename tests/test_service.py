from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from agent_riggs.config import load_config
from agent_riggs.service import RiggsService
from agent_riggs.store import Store


class StubPlugin:
    """Minimal plugin for testing."""

    name = "stub"

    def bind(self, service: RiggsService) -> None:
        self.service = service

    def cli_commands(self) -> list[click.Command]:
        @click.command("stub-cmd")
        def stub_cmd() -> None:
            click.echo("stub")

        return [stub_cmd]

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("riggs://stub", lambda: "stub data")]

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []

    def schema_ddl(self) -> list[str]:
        return ["CREATE TABLE IF NOT EXISTS stub_table (id INTEGER PRIMARY KEY)"]


def test_service_register_plugin(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        service = RiggsService(tmp_project, store, config)
        plugin = StubPlugin()
        service.register(plugin)

        assert "stub" in service.plugins
        assert service.plugin("stub") is plugin
        assert plugin.service is service


def test_service_plugin_schema_applied(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        service = RiggsService(tmp_project, store, config)
        plugin = StubPlugin()
        service.register(plugin)
        store.ensure_schema(plugin.schema_ddl())

        result = store.execute("SELECT count(*) FROM stub_table").fetchone()
        assert result == (0,)


def test_service_plugin_cli_commands(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        service = RiggsService(tmp_project, store, config)
        plugin = StubPlugin()
        service.register(plugin)

        commands = plugin.cli_commands()
        assert len(commands) == 1
        assert commands[0].name == "stub-cmd"


def test_service_unknown_plugin_raises(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        service = RiggsService(tmp_project, store, config)
        import pytest

        with pytest.raises(KeyError):
            service.plugin("nonexistent")
