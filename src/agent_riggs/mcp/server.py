"""MCP server for agent-riggs — auto-discovers resources and tools from plugins."""
from __future__ import annotations
from pathlib import Path
from mcp.server import Server
from agent_riggs.assembly import assemble

def create_server(project_root: Path | None = None) -> Server:
    """Create an MCP server with all plugin resources and tools registered."""
    if project_root is None:
        project_root = Path.cwd()

    service = assemble(project_root, read_only=True)
    server = Server("agent-riggs")

    for plugin in service.plugins.values():
        for uri, handler in plugin.mcp_resources():
            server.read_resource(uri)(handler)

    for plugin in service.plugins.values():
        for name, handler in plugin.mcp_tools():
            server.call_tool(name)(handler)

    return server
