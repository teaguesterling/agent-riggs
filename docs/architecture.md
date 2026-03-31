# Architecture

## Plugin System

Agent Riggs uses a composable plugin architecture. Each subsystem (trust, ingest, ratchet, metrics, briefing, sandbox) is a plugin that implements the `ServicePlugin` protocol:

```python
class ServicePlugin(Protocol):
    name: str
    def bind(self, service: RiggsService) -> None: ...
    def cli_commands(self) -> list[click.Command]: ...
    def mcp_resources(self) -> list[tuple[str, Callable]]: ...
    def mcp_tools(self) -> list[tuple[str, Callable]]: ...
    def schema_ddl(self) -> list[str]: ...
```

Each plugin contributes:
- **Schema DDL** — `CREATE TABLE IF NOT EXISTS` statements for tables it owns
- **CLI commands** — Click commands registered on the main group
- **MCP resources** — URI/handler pairs for read-only resources
- **MCP tools** — Name/handler pairs for agent-callable tools

## Service Layer

`RiggsService` composes plugins. It holds the project root, DuckDB store, and config:

```python
service = RiggsService(project_root, store, config)
service.register(TrustPlugin())
service.register(IngestPlugin())
# ...
```

Cross-plugin access works through the service: `service.plugin("trust").current()`.

## Assembly

`assemble()` builds the service from discovered plugins:

1. Load config (defaults merged with `.riggs/config.toml`)
2. Open DuckDB store
3. Register core plugins (trust, ingest, ratchet, metrics, briefing)
4. Register optional plugins (sandbox — only if blq is on PATH)
5. Execute DDL from all plugins (idempotent schema creation)

The `read_only` parameter controls whether the store allows writes. The MCP server uses `read_only=True`.

## CLI and MCP: Thin Shells

Both the CLI (`cli.py`) and MCP server (`mcp/server.py`) are thin shells over the service layer:

- **CLI** calls `assemble()`, gets a service, calls plugin methods, formats output for the terminal
- **MCP server** calls `assemble(read_only=True)`, auto-discovers resources and tools from plugins

Neither contains business logic. All logic lives in plugins and their backing modules.

## DuckDB Schema

Each plugin owns its tables:

### Trust Plugin

**turns** — every turn from every session:

| Column | Type | Description |
|--------|------|-------------|
| turn_id | BIGINT PK | Unique turn identifier |
| session_id | VARCHAR | Session this turn belongs to |
| project | VARCHAR | Project name |
| turn_number | INTEGER | Turn sequence within session |
| timestamp | TIMESTAMPTZ | When the turn occurred |
| tool_name | VARCHAR | Tool that was called |
| tool_success | BOOLEAN | Whether the call succeeded |
| mode | VARCHAR | Kibitzer mode at time of turn |
| trust_score | DOUBLE | Per-turn score (0-1) |
| trust_1 | DOUBLE | EWMA short window after this turn |
| trust_5 | DOUBLE | EWMA session window after this turn |
| trust_15 | DOUBLE | EWMA baseline window after this turn |
| event_category | VARCHAR | Classification (success, failure, etc.) |
| metadata | JSON | Tool-specific details |

**failure_stream** — failure events with classification:

| Column | Type | Description |
|--------|------|-------------|
| failure_id | BIGINT PK | Unique failure identifier |
| turn_id | BIGINT | Reference to turns table |
| session_id | VARCHAR | Session |
| project | VARCHAR | Project |
| occurred_at | TIMESTAMPTZ | When the failure occurred |
| failure_category | VARCHAR | Classification |
| tool_name | VARCHAR | Tool that failed |
| mode | VARCHAR | Mode at time of failure |
| trust_at_failure | DOUBLE | Trust score when this failure occurred |
| detail | JSON | Failure-specific details |

**session_summaries** — session-level aggregates:

| Column | Type | Description |
|--------|------|-------------|
| session_id | VARCHAR PK | Session identifier |
| project | VARCHAR | Project |
| started_at / ended_at | TIMESTAMPTZ | Session boundaries |
| total_turns / total_failures | INTEGER | Counts |
| failure_rate | DOUBLE | failures / turns |
| trust_start / trust_end / trust_delta | DOUBLE | Trust trajectory |
| modes_used | VARCHAR[] | Modes active during session |
| mode_switches | INTEGER | Number of mode changes |
| structured_tool_fraction | DOUBLE | Fraction using structured tools |
| computation_channel_fraction | DOUBLE | Fraction at computation level 4+ |

### Ratchet Plugin

**ratchet_decisions** — promotion and rejection audit trail:

| Column | Type | Description |
|--------|------|-------------|
| decision_id | BIGINT PK | Unique decision identifier |
| decided_at | TIMESTAMP | When the decision was made |
| candidate_type | VARCHAR | tool_promotion, constraint_promotion, etc. |
| candidate_key | VARCHAR | Human-readable identifier |
| decision | VARCHAR | promoted, rejected, deferred |
| reason | VARCHAR | Human-provided reason |
| evidence | JSON | Frequency, success rate, etc. |
| config_change | JSON | What was changed (audit trail) |

### Sandbox Plugin

**sandbox_profiles** — aggregated execution profiles:

| Column | Type | Description |
|--------|------|-------------|
| command | VARCHAR | Command name (composite PK with project) |
| project | VARCHAR | Project name |
| updated_at | TIMESTAMPTZ | Last update |
| total_runs | INTEGER | Total executions |
| memory_p50/p95/max | BIGINT | Memory usage percentiles |
| duration_p50/p95/max | INTERVAL | Duration percentiles |
| current_spec | JSON | Current sandbox specification |
| current_grade_w | VARCHAR | World coupling grade |
| current_effects_ceiling | INTEGER | Effects ceiling |

## Design Principles

1. **Reads everything, writes nothing (to other tools).** Riggs aggregates data from kibitzer, lackpy, blq, jetsam, and fledgling but never modifies their state. Each tool owns its own storage. Riggs owns `.riggs/store.duckdb` and nothing else.

2. **Human in the loop for promotions.** The ratchet identifies candidates automatically. Applying a promotion requires a human decision (`agent-riggs ratchet promote`). Riggs can recommend trust transitions (specified rules) but cannot expand capabilities.

3. **Specified throughout.** Trust scoring is arithmetic. Failure classification is pattern matching. Candidate identification is SQL. Trend detection is windowed aggregation. No LLM in the analysis loop. Every decision traces to `config.toml` or a SQL query.

4. **DuckDB native.** The store is DuckDB. The queries are SQL. The analytics compose with the rest of the suite's DuckDB usage.

5. **Graceful degradation.** No kibitzer? No primary data source, but everything else works. No blq? Sandbox features disabled. No lackpy? Template promotion disabled. No fledgling? Conversation analytics unavailable. Each missing tool disables a feature, not the system.
