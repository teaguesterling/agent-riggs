"""RiggsService: composable plugin architecture."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_riggs.config import RiggsConfig
from agent_riggs.store import Store

if TYPE_CHECKING:
    from agent_riggs.plugins.base import ServicePlugin


class RiggsService:
    """Composes plugins. CLI and MCP server use this."""

    def __init__(self, project_root: Path, store: Store, config: RiggsConfig) -> None:
        self.project_root = project_root
        self.store = store
        self.config = config
        self._plugins: dict[str, ServicePlugin] = {}

    def register(self, plugin: ServicePlugin) -> None:
        """Register a plugin and bind it to this service."""
        self._plugins[plugin.name] = plugin
        plugin.bind(self)

    def plugin(self, name: str) -> ServicePlugin:
        """Get a registered plugin by name. Raises KeyError if not found."""
        return self._plugins[name]

    @property
    def plugins(self) -> dict[str, ServicePlugin]:
        return dict(self._plugins)
