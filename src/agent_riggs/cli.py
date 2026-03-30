"""CLI entry point for agent-riggs."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

import click

from agent_riggs import __version__


def find_project_root() -> Path:
    """Find the project root (cwd for now)."""
    return Path.cwd()


@click.group()
@click.version_option(__version__, prog_name="agent-riggs")
@click.pass_context
def main(ctx: click.Context) -> None:
    """agent-riggs -- cross-session memory and analysis for the Rigged tool suite."""
    ctx.ensure_object(dict)


@main.command()
def init() -> None:
    """Initialize .riggs/ directory and store."""
    project_root = find_project_root()
    riggs_dir = project_root / ".riggs"
    riggs_dir.mkdir(exist_ok=True)

    config_path = riggs_dir / "config.toml"
    if not config_path.exists():
        defaults_ref = resources.files("agent_riggs") / "defaults" / "config.toml"
        config_path.write_text(defaults_ref.read_text(encoding="utf-8"))

    from agent_riggs.assembly import assemble
    service = assemble(project_root)

    tools = []
    for name in ("kibitzer", "blq", "jetsam", "fledgling"):
        if shutil.which(name) or (project_root / f".{name}").exists():
            tools.append(name)

    click.echo(f"Initialized .riggs/ in {project_root}")
    if tools:
        click.echo(f"Discovered tools: {', '.join(tools)}")
    else:
        click.echo("No sibling tools discovered yet.")

    service.store.close()


@main.command()
def ingest() -> None:
    """Ingest session data from sibling tools."""
    from agent_riggs.assembly import assemble

    project_root = find_project_root()
    service = assemble(project_root)

    ingest_plugin = service.plugin("ingest")
    result = ingest_plugin.run()

    click.echo(f"Ingested {result.turns_ingested} turns from {result.sources_read}")
    if result.failures_recorded:
        click.echo(f"Recorded {result.failures_recorded} failures")

    service.store.close()


@main.command()
def status() -> None:
    """Show trust scores, mode, and ratchet summary."""
    from agent_riggs.assembly import assemble

    project_root = find_project_root()
    service = assemble(project_root)

    trust_plugin = service.plugin("trust")
    data = trust_plugin.current()

    if not data["has_data"]:
        click.echo("trust: no data yet")
        click.echo("\nRun `agent-riggs ingest` after a session.")
    else:
        click.echo(
            f"trust: {data['trust_1']:.2f} / {data['trust_5']:.2f} / {data['trust_15']:.2f}"
        )
        click.echo("       now    session  baseline")

    service.store.close()
