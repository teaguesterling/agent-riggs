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
    from agent_riggs.trust.ledger import TrustLedger

    service = assemble(project_root)

    # Create the out-of-tree trust state dir + signing key up front.
    ledger = TrustLedger(project_root)
    ledger.ensure_initialized()

    tools = []
    for name in ("kibitzer", "blq", "jetsam", "fledgling"):
        if shutil.which(name) or (project_root / f".{name}").exists():
            tools.append(name)

    click.echo(f"Initialized .riggs/ in {project_root}")
    click.echo(f"Trust state directory: {ledger.dir}")
    if tools:
        click.echo(f"Discovered tools: {', '.join(tools)}")
    else:
        click.echo("No sibling tools discovered yet.")

    service.store.close()


@main.command()
def ingest() -> None:
    """Ingest session data from sibling tools."""
    from agent_riggs.assembly import assemble
    from agent_riggs.trust.ledger import LedgerIntegrityError

    project_root = find_project_root()
    service = assemble(project_root)

    ingest_plugin = service.plugin("ingest")
    try:
        result = ingest_plugin.run()
    except LedgerIntegrityError as exc:
        click.echo(f"REFUSED: {exc}", err=True)
        service.store.close()
        raise SystemExit(2) from exc

    click.echo(f"Ingested {result.turns_ingested} turns from {result.sources_read}")
    if result.duplicates_skipped:
        click.echo(f"Skipped {result.duplicates_skipped} already-recorded events")
    if result.trials_ingested:
        click.echo(f"Ingested {result.trials_ingested} nudge trials")
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
        if data.get("state") == "tampered":
            click.echo("trust: STATE FAILED INTEGRITY VERIFICATION (fail closed, low trust)")
            click.echo(f"       {data.get('detail', '')}")
        else:
            click.echo("trust: no verified data yet (low trust)")
            click.echo("\nRun `agent-riggs ingest` after a session.")
    else:
        click.echo(
            f"trust: {data['trust_1']:.2f} / {data['trust_5']:.2f} / {data['trust_15']:.2f}"
        )
        click.echo("       now    session  baseline")

    service.store.close()


# --- Gate command ---


@main.command("gate")
def gate_cmd() -> None:
    """Fail-closed trust gate check (exit 0 = allow, 2 = deny).

    Intended for harness hooks: consult this before granting the agent
    expanded capability. Denies on absent/tampered trust state, low trust,
    or recent violations.
    """
    from agent_riggs.trust.gate import TrustGate

    decision = TrustGate(find_project_root()).check()
    verdict = "ALLOW" if decision.allowed else "DENY"
    click.echo(f"{verdict}: {decision.reason}")
    click.echo(
        f"trust: {decision.trust_1:.2f} / {decision.trust_5:.2f} / {decision.trust_15:.2f} "
        f"(state: {decision.state})"
    )
    if not decision.allowed:
        raise SystemExit(2)


# --- Trust commands ---


@main.group("trust")
def trust_group() -> None:
    """Trust score commands."""


@trust_group.command("current")
def trust_current() -> None:
    """Show current trust scores."""
    from agent_riggs.assembly import assemble

    service = assemble(find_project_root())
    data = service.plugin("trust").current()
    if not data["has_data"]:
        click.echo("No trust data yet.")
    else:
        click.echo(f"trust_1 (now):      {data['trust_1']:.4f}")
        click.echo(f"trust_5 (session):  {data['trust_5']:.4f}")
        click.echo(f"trust_15 (baseline):{data['trust_15']:.4f}")
    service.store.close()


@trust_group.command("history")
@click.option("--limit", default=20, help="Number of entries")
def trust_history(limit: int) -> None:
    """Show trust score history."""
    from agent_riggs.assembly import assemble

    service = assemble(find_project_root())
    history = service.plugin("trust").history(limit=limit)
    if not history:
        click.echo("No trust history.")
    else:
        for entry in history:
            click.echo(
                f"  [{entry['session_id']}:{entry['turn_number']}] "
                f"{entry['trust_1']:.2f} / {entry['trust_5']:.2f} / {entry['trust_15']:.2f}"
            )
    service.store.close()


# --- Ratchet commands ---


@main.group("ratchet")
def ratchet_group() -> None:
    """Ratchet candidate commands."""


@ratchet_group.command("candidates")
def ratchet_candidates() -> None:
    """Show pending ratchet candidates."""
    from agent_riggs.assembly import assemble

    service = assemble(find_project_root())
    candidates = service.plugin("ratchet").candidates()
    if not candidates:
        click.echo("No ratchet candidates.")
    else:
        for c in candidates:
            click.echo(f"\n  [{c.candidate_type}] {c.candidate_key}")
            click.echo(f"    {c.recommendation}")
            click.echo(f"    Evidence: {c.evidence}")
    service.store.close()


@ratchet_group.command("promote")
@click.argument("key")
@click.option("--reason", default=None, help="Reason for promotion")
def ratchet_promote(key: str, reason: str | None) -> None:
    """Promote a ratchet candidate."""
    from agent_riggs.assembly import assemble

    service = assemble(find_project_root())
    try:
        service.plugin("ratchet").promote(key, reason)
        click.echo(f"Promoted: {key}")
    except KeyError:
        click.echo(f"No candidate with key: {key}", err=True)
    except PermissionError as exc:
        click.echo(f"DENIED: {exc}", err=True)
        service.store.close()
        raise SystemExit(2) from exc
    service.store.close()


@ratchet_group.command("reject")
@click.argument("key")
@click.option("--reason", required=True, help="Reason for rejection")
def ratchet_reject(key: str, reason: str) -> None:
    """Reject a ratchet candidate with reason."""
    from agent_riggs.assembly import assemble

    service = assemble(find_project_root())
    try:
        service.plugin("ratchet").reject(key, reason)
        click.echo(f"Rejected: {key}")
    except KeyError:
        click.echo(f"No candidate with key: {key}", err=True)
    service.store.close()


@ratchet_group.command("history")
def ratchet_history() -> None:
    """Show ratchet decision history."""
    from agent_riggs.assembly import assemble

    service = assemble(find_project_root())
    history = service.plugin("ratchet").history()
    if not history:
        click.echo("No ratchet decisions recorded.")
    else:
        for h in history:
            click.echo(
                f"  [{h['decided_at']}] {h['decision']}: "
                f"{h['candidate_key']} — {h.get('reason', '')}"
            )
    service.store.close()


# --- Metrics command ---


@main.command("metrics")
@click.option("--period", default=None, type=int, help="Period in days")
def metrics_cmd(period: int | None) -> None:
    """Show ratchet metrics dashboard."""
    from agent_riggs.assembly import assemble

    service = assemble(find_project_root())
    m = service.plugin("metrics").compute(period)
    click.echo(f"RATCHET METRICS ({m.total_sessions} sessions)\n")
    click.echo(f"  Ratchet velocity:        {m.ratchet_velocity} promotions")
    click.echo(f"  Self-service ratio:      {m.structured_tool_fraction:.0%} structured")
    click.echo(f"  Computation channel %:   {m.computation_channel_fraction:.0%}")
    click.echo(
        f"  Trust trajectory:        {m.trust_trajectory_start:.2f} -> "
        f"{m.trust_trajectory_end:.2f}"
    )
    click.echo(f"  Failure rate:            {m.failure_rate:.0%}")
    if m.mode_distribution:
        click.echo("\n  Mode distribution:")
        for mode, frac in sorted(m.mode_distribution.items(), key=lambda x: -x[1]):
            click.echo(f"    {mode}: {frac:.0%}")
    service.store.close()


# --- Brief command ---


@main.command("brief")
def brief_cmd() -> None:
    """Full session briefing."""
    from agent_riggs.assembly import assemble

    service = assemble(find_project_root())
    briefing = service.plugin("briefing").brief()
    click.echo(f"PROJECT BRIEFING: {find_project_root().name}\n")
    click.echo(briefing.format())
    service.store.close()
