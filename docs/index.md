# Agent Riggs Documentation

*The one who shows up the next morning having gone through all the case files.*

Agent Riggs is the cross-session memory and analysis layer for the [Rigged](https://github.com/teague/rigged) tool suite. It watches what happens across sessions — trust scores, failure patterns, tool usage — and surfaces recommendations that make the system better over time.

## Guides

- **[Tutorial](tutorial.md)** — Start here. Walk through setup, ingestion, trust scores, the ratchet, and metrics with hands-on examples.
- **[The Ratchet](the-ratchet.md)** — The conceptual core. How the system evolves: trust informs transitions, patterns become templates, failed delegations reveal missing tools.

## Reference

- **[CLI Reference](cli-reference.md)** — Every command, every flag, with example output.
- **[Configuration](configuration.md)** — Complete `.riggs/config.toml` reference.
- **[Integration](integration.md)** — How Riggs connects to kibitzer, lackpy, blq, jetsam, and fledgling.
- **[Architecture](architecture.md)** — Plugin system, service layer, DuckDB schema, design principles.
- **[MCP Server](mcp.md)** — Resources and tools for agent access.

## Quick Start

```bash
pip install agent-riggs
cd your-project/
agent-riggs init
# ... run a session with kibitzer ...
agent-riggs ingest
agent-riggs status
```
