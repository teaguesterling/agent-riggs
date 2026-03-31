# MCP Server Reference

Agent Riggs exposes an MCP (Model Context Protocol) server that agents can access during a session. The server is **read-only** — agents can observe trust data and metrics but cannot modify the store.

## Starting the Server

The MCP server is registered during `agent-riggs init`. It auto-discovers resources and tools from all registered plugins.

## Resources

Resources are always available and can be included in the system prompt or accessed on demand.

| URI | Content | Source Plugin |
|-----|---------|---------------|
| `riggs://briefing` | Session briefing — trust baseline, last session summary, known issues, active candidates | briefing |
| `riggs://trust` | Current trust scores (trust_1, trust_5, trust_15) with trajectory | trust |
| `riggs://ratchet` | Pending ratchet candidates and recent promotion/rejection decisions | ratchet |
| `riggs://metrics` | Ratchet metrics — velocity, self-service ratio, failure rate, mode distribution | metrics |
| `riggs://sandbox` | Sandbox grades and tightening recommendations (when blq is available) | sandbox |

### Example: riggs://briefing

```
Trust baseline: 0.87
Last session: sess-abc, 34 turns, trust 0.91
Known issues:
  - edit_failure (12 occurrences)
Active ratchet candidates: 2
```

### Example: riggs://trust

```
trust: 0.94 / 0.71 / 0.87
       now    session  baseline
```

## Tools

Tools are callable by agents via MCP tool calls.

### RiggsTrust

Get trust scores, optionally with history.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `window` | int | No | Number of historical entries to include |

**Without window:** Returns current trust_1, trust_5, trust_15.

**With window:** Returns current scores plus the last N trust entries.

### RiggsMetrics

Get ratchet metrics for a time period.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `period` | int | No | Analysis window in days (default: 30) |

Returns: total_sessions, total_turns, ratchet_velocity, structured_tool_fraction, computation_channel_fraction, trust_trajectory, failure_rate, mode_distribution.

### RiggsFailures

Query the cross-session failure stream.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | str | No | Filter to a specific failure category |
| `limit` | int | No | Maximum entries to return (default: 20) |

Returns: failure entries grouped by category with counts and affected sessions.

### RiggsSandbox

Get sandbox grades and recommendations.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | str | No | Filter to a specific command |

Returns: sandbox profiles with grades, headroom, and tightening recommendations. Only available when blq is installed.

## Read-Only Guarantee

The MCP server opens the DuckDB store with `read_only=True`. This is enforced structurally — the database connection rejects any write operation. Agents can query freely without risk of data corruption.

All mutations go through the CLI (`agent-riggs ingest`, `agent-riggs ratchet promote`, etc.) which requires human action.
