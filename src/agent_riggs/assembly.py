"""Build a RiggsService from discovered plugins."""

from __future__ import annotations

from pathlib import Path

from agent_riggs.config import load_config
from agent_riggs.service import RiggsService
from agent_riggs.store import Store


def assemble(project_root: Path, read_only: bool = False) -> RiggsService:
    """Build the service with all discovered plugins."""
    config = load_config(project_root)
    store_path = project_root / config.store.path
    store = Store(store_path, read_only=read_only)
    service = RiggsService(project_root, store, config)

    _register_core_plugins(service)
    _register_optional_plugins(service)

    ddl: list[str] = []
    for p in service.plugins.values():
        ddl.extend(p.schema_ddl())
    if not read_only:
        store.ensure_schema(ddl)

    return service


def _register_core_plugins(service: RiggsService) -> None:
    """Register plugins that are always available."""
    from agent_riggs.plugins.trust import TrustPlugin
    from agent_riggs.plugins.ingest import IngestPlugin
    from agent_riggs.plugins.ratchet import RatchetPlugin
    from agent_riggs.plugins.metrics import MetricsPlugin
    from agent_riggs.plugins.briefing import BriefingPlugin

    service.register(TrustPlugin())
    service.register(IngestPlugin())
    service.register(RatchetPlugin())
    service.register(MetricsPlugin())
    service.register(BriefingPlugin())


def _register_optional_plugins(service: RiggsService) -> None:
    """Register plugins whose backing tools may not be installed."""
    import shutil

    if shutil.which("blq"):
        from agent_riggs.plugins.sandbox import SandboxPlugin
        service.register(SandboxPlugin())
