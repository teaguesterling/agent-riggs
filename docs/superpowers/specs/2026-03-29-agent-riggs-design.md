# Agent Riggs Design Spec

Cross-session memory and analysis layer for the Rigged tool suite. Implements Beer's System 3* — audit and intelligence across sessions, informing kibitzer's within-session control.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Package name | `agent_riggs` (`src/agent_riggs/`) | Matches PyPI name `agent-riggs`, avoids collision |
| Schema management | Idempotent `CREATE TABLE IF NOT EXISTS` | Simple, sufficient for early stage. Migrations later if needed |
| Ingest architecture | Pull-based with optional MCP polling | Matches "between sessions" design. No daemon required |
| Service layer | Composable plugin architecture | Each subsystem is a plugin. CLI and MCP are thin shells |
| Build system | Hatchling | Consistent with kibitzer and jetsam |

## Package Structure

```
agent-riggs/
├── pyproject.toml
├── src/agent_riggs/
│   ├── __init__.py
│   ├── config.py                   # Load/merge .riggs/config.toml with defaults
│   ├── store.py                    # DuckDB open/close, schema from plugins
│   ├── service.py                  # RiggsService: plugin composition
│   ├── assembly.py                 # Build service from discovered plugins
│   ├── defaults/
│   │   └── config.toml             # Shipped default configuration
│   ├── plugins/
│   │   ├── __init__.py
│   │   ├── base.py                 # ServicePlugin protocol
│   │   ├── trust.py                # Trust scoring, EWMA, transitions
│   │   ├── ingest.py               # Pull events from sibling tools
│   │   ├── ratchet.py              # Candidates, promotions, history
│   │   ├── sandbox.py              # blq integration, grades, recommendations
│   │   ├── metrics.py              # Ratchet velocity, trends
│   │   └── briefing.py             # Session and project briefings
│   ├── trust/
│   │   ├── __init__.py
│   │   ├── scorer.py               # score_event() pure function
│   │   ├── ewma.py                 # TrustEWMA class
│   │   ├── events.py               # TurnEvent dataclass, classify_event()
│   │   └── transitions.py          # recommend_transition()
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── pipeline.py             # Orchestrate: discover -> read -> classify -> score -> store
│   │   └── sources/
│   │       ├── __init__.py
│   │       ├── base.py             # Source protocol
│   │       ├── kibitzer.py         # .kibitzer/state.json + intercept.log
│   │       ├── blq.py              # .lq/blq.duckdb
│   │       ├── jetsam.py           # .jetsam/ state
│   │       └── fledgling.py        # fledgling access log
│   ├── ratchet/
│   │   ├── __init__.py
│   │   ├── aggregator.py           # Cross-session failure stream queries
│   │   ├── candidates.py           # SQL-based candidate identification
│   │   ├── promotions.py           # Apply/reject, write config changes
│   │   └── history.py              # Decision tracking
│   ├── sandbox/
│   │   ├── __init__.py
│   │   ├── grades.py               # Aggregate blq sandbox data
│   │   ├── recommendations.py      # Tightening logic
│   │   └── integration.py          # Shell out to blq CLI
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── compute.py              # Ratchet velocity, self-service ratio
│   │   └── trends.py               # Windowed trend detection
│   ├── briefing/
│   │   ├── __init__.py
│   │   ├── session.py              # Session briefing
│   │   └── project.py              # Project health
│   ├── cli.py                      # Click group, auto-discovers plugin commands
│   └── mcp/
│       └── server.py               # Auto-discovers plugin resources + tools
├── tests/
│   ├── conftest.py
│   ├── test_store.py
│   ├── test_config.py
│   ├── test_service.py
│   ├── test_trust/
│   │   ├── test_scorer.py
│   │   ├── test_ewma.py
│   │   └── test_transitions.py
│   ├── test_ingest/
│   │   ├── test_pipeline.py
│   │   └── test_sources/
│   │       └── test_kibitzer.py
│   ├── test_ratchet/
│   │   └── test_candidates.py
│   └── test_metrics/
│       └── test_compute.py
└── README.md
```

## Core Interfaces

### Store

```python
class Store:
    def __init__(self, path: Path, read_only: bool = False):
        self.conn = duckdb.connect(str(path), read_only=read_only)

    def ensure_schema(self, ddl_statements: list[str]) -> None:
        """Execute DDL from all plugins. Idempotent."""
        for ddl in ddl_statements:
            self.conn.execute(ddl)

    def execute(self, query: str, params=None):
        return self.conn.execute(query, params)

    def close(self):
        self.conn.close()
```

### Service & Plugin Protocol

```python
class ServicePlugin(Protocol):
    name: str

    def bind(self, service: RiggsService) -> None:
        """Receive service reference for cross-plugin access."""

    def cli_commands(self) -> list[click.Command]:
        """Commands this plugin contributes to the CLI."""

    def mcp_resources(self) -> list[tuple[str, Callable]]:
        """(uri, handler) pairs for MCP resources."""

    def mcp_tools(self) -> list[tuple[str, Callable]]:
        """(name, handler) pairs for MCP tools."""

    def schema_ddl(self) -> str:
        """DDL for tables this plugin owns."""


class RiggsService:
    def __init__(self, project_root: Path, store: Store, config: RiggsConfig):
        self.project_root = project_root
        self.store = store
        self.config = config
        self._plugins: dict[str, ServicePlugin] = {}

    def register(self, plugin: ServicePlugin) -> None:
        self._plugins[plugin.name] = plugin
        plugin.bind(self)

    def plugin(self, name: str) -> ServicePlugin:
        return self._plugins[name]

    @property
    def plugins(self) -> dict[str, ServicePlugin]:
        return dict(self._plugins)
```

### Assembly

```python
def assemble(project_root: Path, read_only: bool = False) -> RiggsService:
    config = load_config(project_root)
    store = Store(config.store.path, read_only=read_only)
    service = RiggsService(project_root, store, config)

    # Core plugins
    service.register(TrustPlugin())
    service.register(IngestPlugin())
    service.register(RatchetPlugin())
    service.register(MetricsPlugin())
    service.register(BriefingPlugin())

    # Optional plugins (graceful degradation)
    if shutil.which("blq"):
        service.register(SandboxPlugin())

    store.ensure_schema([p.schema_ddl() for p in service.plugins.values()])
    return service
```

### CLI Shell

```python
@click.group()
@click.pass_context
def main(ctx):
    ctx.obj = assemble(find_project_root())

# Auto-discover commands from registered plugins
for plugin in service.plugins.values():
    for cmd in plugin.cli_commands():
        main.add_command(cmd)
```

### MCP Shell

```python
service = assemble(find_project_root(), read_only=True)

for plugin in service.plugins.values():
    for uri, handler in plugin.mcp_resources():
        server.resource(uri)(handler)
    for name, handler in plugin.mcp_tools():
        server.tool(name)(handler)
```

## Trust Engine

### Events

```python
@dataclass
class TurnEvent:
    session_id: str
    turn_number: int
    timestamp: datetime
    tool_name: str | None
    tool_success: bool | None
    mode: str | None
    event_category: str     # success, path_denial, edit_failure, etc.
    metadata: dict
```

### Scoring

Pure function. Maps event category to configured score:

| Event | Default Score |
|-------|---------------|
| Successful tool call in correct mode | 1.0 |
| Successful tool call, suboptimal tool | 0.7 |
| Mode switch (agent-initiated) | 0.8 |
| Mode switch (controller-initiated) | 0.3 |
| Failed tool call | 0.2 |
| Path guard denial | 0.1 |
| Repeated failure (same pattern) | 0.0 |

All configurable in `.riggs/config.toml`.

### EWMA

Three windows, three multiplications per turn:

```python
class TrustEWMA:
    def __init__(self, alpha_short=0.4, alpha_session=0.08, alpha_baseline=0.02):
        self.t1 = self.t5 = self.t15 = 1.0

    def update(self, score: float) -> tuple[float, float, float]:
        self.t1 = self.t1 * (1 - self.alpha_short) + score * self.alpha_short
        self.t5 = self.t5 * (1 - self.alpha_session) + score * self.alpha_session
        self.t15 = self.t15 * (1 - self.alpha_baseline) + score * self.alpha_baseline
        return (self.t1, self.t5, self.t15)
```

### Trust-Informed Transitions

| Condition | Action |
|-----------|--------|
| trust_1 < 0.3 | Recommend tightening |
| trust_1 < 0.3 AND trust_5 < 0.5 | Auto-tighten |
| trust_5 declining 10+ turns | Coach message |
| trust_1 > 0.9 AND trust_5 > 0.8 for 20+ turns | Suggest loosening |
| trust_15 < 0.5 | Flag project config |

Recommendations written to `.kibitzer/state.json`. Riggs never enforces directly.

## Ingest Pipeline

### Source Protocol

```python
class Source(Protocol):
    name: str
    def discover(self, project_root: Path) -> bool: ...
    def read_events(self, project_root: Path, since: datetime | None) -> list[TurnEvent]: ...
```

### Sources

| Source | Reads from | Graceful when missing |
|--------|-----------|----------------------|
| Kibitzer | `.kibitzer/state.json`, `.kibitzer/intercept.log` | Yes — core source |
| blq | `.lq/blq.duckdb` | Yes — sandbox features disabled |
| Jetsam | `.jetsam/` state files | Yes — commit pattern analysis disabled |
| Fledgling | Fledgling access log | Yes — conversation analytics disabled |

### Pipeline

```python
def ingest(store, project_root, sources, since=None) -> IngestResult:
    for source in sources:
        if source.discover(project_root):
            events = source.read_events(project_root, since)
            for event in events:
                score = score_event(event, config.trust)
                ewma.update(score)
                store_turn(store, event, score, ewma.snapshot())
                if is_failure(event):
                    store_failure(store, event, score)
    return IngestResult(...)
```

## Storage Schema

Owned per-plugin. Each plugin's `schema_ddl()` returns its tables.

### Trust Plugin Tables

```sql
CREATE TABLE IF NOT EXISTS turns (
    turn_id         BIGINT PRIMARY KEY,
    session_id      VARCHAR NOT NULL,
    project         VARCHAR NOT NULL,
    turn_number     INTEGER NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    tool_name       VARCHAR,
    tool_success    BOOLEAN,
    mode            VARCHAR,
    trust_score     DOUBLE,
    trust_1         DOUBLE,
    trust_5         DOUBLE,
    trust_15        DOUBLE,
    event_category  VARCHAR,
    metadata        JSON
);

CREATE TABLE IF NOT EXISTS failure_stream (
    failure_id       BIGINT PRIMARY KEY,
    turn_id          BIGINT,
    session_id       VARCHAR NOT NULL,
    project          VARCHAR NOT NULL,
    occurred_at      TIMESTAMPTZ NOT NULL,
    failure_category VARCHAR NOT NULL,
    tool_name        VARCHAR,
    mode             VARCHAR,
    trust_at_failure DOUBLE,
    detail           JSON
);

CREATE TABLE IF NOT EXISTS session_summaries (
    session_id      VARCHAR PRIMARY KEY,
    project         VARCHAR NOT NULL,
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration        INTERVAL,
    total_turns     INTEGER,
    total_failures  INTEGER,
    failure_rate    DOUBLE,
    trust_start     DOUBLE,
    trust_end       DOUBLE,
    trust_delta     DOUBLE,
    modes_used      VARCHAR[],
    mode_switches   INTEGER,
    computation_channel_fraction DOUBLE,
    structured_tool_fraction     DOUBLE
);
```

### Ratchet Plugin Tables

```sql
CREATE TABLE IF NOT EXISTS ratchet_decisions (
    decision_id     BIGINT PRIMARY KEY,
    decided_at      TIMESTAMPTZ NOT NULL,
    candidate_type  VARCHAR NOT NULL,
    candidate_key   VARCHAR NOT NULL,
    decision        VARCHAR NOT NULL,
    reason          VARCHAR,
    evidence        JSON,
    config_change   JSON
);
```

### Sandbox Plugin Tables

```sql
CREATE TABLE IF NOT EXISTS sandbox_profiles (
    command         VARCHAR NOT NULL,
    project         VARCHAR NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    total_runs      INTEGER,
    memory_p50      BIGINT,
    memory_p95      BIGINT,
    memory_max      BIGINT,
    duration_p50    INTERVAL,
    duration_p95    INTERVAL,
    duration_max    INTERVAL,
    current_spec    JSON,
    current_grade_w VARCHAR,
    current_effects_ceiling INTEGER,
    PRIMARY KEY (command, project)
);
```

### Ratchet Candidate Views

Defined as SQL views by the ratchet plugin, querying turns and failure_stream tables owned by the trust plugin. Cross-plugin table access is fine — same DuckDB instance, and the trust plugin owns the schema while other plugins read from it.

## Ratchet Subsystem

### Candidates

Two SQL views identify candidates:

- **Tool promotion**: Bash patterns with frequency >= 5, sessions >= 3, success_rate >= 0.8, and a known structured alternative
- **Constraint promotion**: Repeated failures at the same boundary (category + tool + mode) with occurrences >= 3

Thresholds configurable in `[ratchet]` config section.

### Promotions

`ratchet promote` writes to sibling tool configs:
- Kibitzer interceptor graduation: updates `.kibitzer/config.toml` `[plugins.X] mode`
- Sandbox tightening: delegates to `blq sandbox tighten`
- Constraint documentation: suggests CLAUDE.md additions (human writes)

Every decision (promote, reject, defer) recorded in `ratchet_decisions` table with evidence and config change for audit.

## MCP Server

### Resources (read-only)

| URI | Source Plugin | Content |
|-----|--------------|---------|
| `riggs://briefing` | briefing | Session briefing markdown |
| `riggs://trust` | trust | Current t1/t5/t15 + trajectory |
| `riggs://ratchet` | ratchet | Pending candidates + recent decisions |
| `riggs://sandbox` | sandbox | Grades + recommendations |
| `riggs://metrics` | metrics | Ratchet metrics markdown |

### Tools (read-only)

| Tool | Source Plugin | Parameters |
|------|--------------|------------|
| `RiggsTrust` | trust | `window?` |
| `RiggsMetrics` | metrics | `period?` |
| `RiggsFailures` | ratchet | `category?`, `limit?` |
| `RiggsSandbox` | sandbox | `command?` |

MCP server opens store in `read_only=True` mode. Agent can read but never mutate.

## Configuration

`.riggs/config.toml` with defaults shipped in package. User config merges over defaults.

Sections: `[trust]`, `[ratchet]`, `[sandbox]`, `[metrics]`, `[store]`. Each maps to a typed dataclass consumed by the corresponding plugin.

## Dependencies

```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "duckdb>=1.0",
    "mcp[cli]>=1.0",
    "tomli-w>=1.0",
]

[project.optional-dependencies]
full = ["kibitzer", "fledgling", "blq", "jetsam"]
dev = ["pytest", "pytest-asyncio", "ruff", "mypy"]
```

Python 3.11+ because `tomllib` is stdlib and `X | Y` union syntax is clean.

## Build Order

1. **Store + config + plugin protocol** — foundation
2. **Trust engine** — scorer, EWMA, events, transitions
3. **Trust plugin** — wire trust into service layer with schema DDL
4. **Ingest pipeline + kibitzer source** — events flowing into store
5. **Ingest plugin** — wire into service
6. **CLI shell + init/status/trust commands** — first usable output
7. **Ratchet plugin** — aggregation, candidates, promotions
8. **Metrics plugin** — computed from store
9. **Briefing plugin** — composes trust + ratchet + metrics
10. **Sandbox plugin** — blq integration (optional)
11. **MCP server** — auto-discovered from plugins
12. **CLI remaining commands** — ratchet, sandbox, metrics, brief

Each step is testable independently. Steps 1-6 produce a working `agent-riggs status` command.
