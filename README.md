# Agent Riggs

> The one who shows up the next morning having gone through all the case files.

Agent Riggs is the **cross-session memory and analysis layer for the Rigged tool suite**. It implements Beer's System 3* — audit and intelligence across sessions — to inform kibitzer's within-session control.

Riggs tracks agent behavior across sessions using a trust-scoring system, identifies patterns of failure and success, recommends tool and constraint promotions (ratcheting), and provides session briefings to help agents understand their performance context.

## Installation

```bash
pip install agent-riggs
agent-riggs init
```

This creates a `.riggs/` directory with configuration and a DuckDB store for cross-session analysis.

## What It Does

### Trust Scoring
Riggs uses a **3-window exponential weighted moving average (EWMA)** similar to uptime monitoring:
- **t1** (immediate, α=0.4): Last ~2–3 turns
- **t5** (session, α=0.08): Last ~50–60 turns
- **t15** (baseline, α=0.02): Project lifetime

Each turn is scored (0.0–1.0) based on event type: successful tool calls, mode switches, failures, constraint violations.

Scores are integrity-protected (see [Trust Integrity](docs/trust-integrity.md)):
- Authoritative trust state lives in an **append-only, HMAC-chained ledger
  outside the project tree** — not in the project-local DuckDB store, which is
  analytics only. Deleting or editing project files never raises trust.
- Events are tagged **observed** (independently recorded outcomes, e.g. blq
  exit codes) or **self-reported** (the session's own claims). Self-reported
  events can hold or lower trust but never raise it.
- An unknown subject starts **low** (`initial_trust`, default 0.4) and accrues
  trust from observed evidence. Absent or tampered state reads as low trust —
  fail closed, never fail open.

### Trust-Informed Transitions and the Gate
Riggs monitors trust windows and recommends tightening/loosening:
- t1 < 0.3: Recommend tightening
- t1 < 0.3 AND t5 < 0.5: Auto-tighten
- t1 > 0.9 AND t5 > 0.8 held for 20+ consecutive turns: Suggest loosening
- t15 < 0.5: Flag project config

Recommendations are written to `.kibitzer/state.json` after each ingest for
kibitzer's mode controller to act on. Capability-expanding decisions
additionally pass through the **fail-closed trust gate** (`agent-riggs gate`,
the `RiggsGate` MCP tool, and tool promotions): the gate denies on absent or
unverifiable trust state, insufficient trust, or recent violations. Mode
control stays with kibitzer; the gate is the enforcement point riggs itself
guarantees.

### Cross-Session Failure Stream
Riggs ingests turn data from kibitzer and builds a cross-session failure stream. Each failure is categorized (path denial, edit failure, mode violation, etc.) and stored with the trust score at failure time.

### Ratchet Candidates
Riggs identifies two types of promotion candidates:

| Candidate Type | Criteria | Action |
|---|---|---|
| **Nudged tool promotion** | Enough kibitzer A/B nudge trials AND measured heed rate AND heed lift over the control arm (frequency alone never qualifies) | Escalate the kibitzer interceptor (`[plugins.X] mode` suggest → redirect) via human-gated `ratchet promote` |
| **Constraint promotion** | Repeated failures at same boundary (category + tool + mode) ≥ 3 occurrences | Tighten or document constraint |

Tool promotions are gated on *causal* evidence from kibitzer's nudge A/B
experiment (`~/.kibitzer/nudge_trials.jsonl`), not raw bypass frequency —
a bypass pattern that fires constantly but is never heeded is surfaced as
evidence in the briefing yet never becomes a candidate.

### Sandbox Intelligence
If `blq` is installed, Riggs integrates sandbox profiling data to recommend resource tightening. Tracks memory and duration percentiles across runs.

### Ratchet Metrics
Computes and trends:
- Ratchet velocity (promotions/session)
- Self-service ratio (tools without controller intervention)
- Mode switch frequency
- Failure rate trends

### Session Briefing
Riggs composes session briefings from trust, ingest, ratchet, and metrics data — what happened recently per source (builds/tests via blq, git workflow via jetsam, tool usage via fledgling, intercepted bypasses via kibitzer), the nudge A/B evidence and whether anything qualifies for promotion, known failure patterns, and pending candidates.

### Incremental Ingest
Every source tracks a high-water mark (a JSON cursor in the `ingest_state` table), so `agent-riggs ingest` only reads new data on each run — re-running is fast and idempotent, which keeps the SessionStart hook well under its time budget.

## Architecture

### Composable Plugin Service Layer

Every subsystem is a **plugin** that registers:
- **CLI commands** — contributed to the main command group
- **MCP resources** — read-only data resources for agents
- **MCP tools** — read-only query/analysis tools for agents
- **Schema DDL** — tables owned by this plugin

The CLI and MCP server are thin shells that auto-discover and compose from registered plugins.

### Plugins

| Plugin | Responsibility |
|---|---|
| **trust** | Event scoring, EWMA, trust windows, transition recommendations |
| **ingest** | Discover and read events from sibling tools (kibitzer, blq, jetsam, fledgling, lackpy) plus kibitzer nudge trials; incremental via per-source cursors |
| **ratchet** | Identify promotion candidates, track decisions, manage promotions |
| **sandbox** | Integrate blq profiling, generate tightening recommendations |
| **metrics** | Compute ratchet velocity, trends, self-service ratio |
| **briefing** | Compose session and project briefings from other plugins |

### DuckDB Persistence

Analytics data (turns, failure stream, ratchet decisions, metrics) is stored in a local DuckDB database (`.riggs/store.duckdb`). Schema is managed idempotently — plugins declare their tables via `CREATE TABLE IF NOT EXISTS`. No migrations or daemon required.

The authoritative **trust state** does not live here: it lives in an append-only, HMAC-chained ledger outside the project tree, so the scored agent cannot reset or rewrite it. See [Trust Integrity](docs/trust-integrity.md).

## Usage

### CLI Commands

```bash
agent-riggs init                    # Initialize .riggs/ config, store, and trust state dir
agent-riggs ingest                  # Pull events from sibling tools (kibitzer, blq, etc.)
agent-riggs gate                    # Fail-closed trust gate check (exit 0 allow / 2 deny)
agent-riggs status                  # Show current trust scores and recent events
agent-riggs trust [--window {1,5,15}]
                                    # Display trust window and trajectory
agent-riggs ratchet [--candidate {tool,constraint}]
                                    # Show ratchet candidates and recent decisions
agent-riggs sandbox [--command CMD]
                                    # Show sandbox profiles and recommendations
agent-riggs metrics [--period DAYS]
                                    # Display ratchet velocity, trends, metrics
agent-riggs brief [--type {session,project}]
                                    # Generate session or project briefing
```

### MCP Server

Start the MCP server for integration with agents:

```bash
agent-riggs serve
```

Agents can then access:

**Resources** (read-only):
- `riggs://briefing` — Session briefing markdown
- `riggs://trust` — Current t1/t5/t15 + trajectory
- `riggs://ratchet` — Pending candidates + recent decisions
- `riggs://sandbox` — Grades + recommendations
- `riggs://metrics` — Ratchet metrics markdown

**Tools** (read-only):
- `RiggsTrust` — Query trust window and history
- `RiggsGate` — Fail-closed gate decision for capability-expanding actions
- `RiggsMetrics` — Compute metrics over a period
- `RiggsFailures` — Query failure stream by category
- `RiggsSandbox` — Get sandbox profile for a command

## Configuration

### .riggs/config.toml

Configuration is loaded from `.riggs/config.toml` with sensible defaults shipped in the package. User config merges over defaults — **except the `[trust]` section**: trust scoring and gate policy are never read from the project tree (the scored agent can edit it). Trust policy comes from the shipped defaults, optionally overridden by `policy.toml` in the out-of-tree state directory (see [Trust Integrity](docs/trust-integrity.md)).

Example sections:

```toml
[trust]
# Event scoring weights (0.0 - 1.0)
success_correct_mode = 1.0
success_suboptimal_tool = 0.7
mode_switch_agent = 0.8
mode_switch_controller = 0.3
tool_failure = 0.2
path_denial = 0.1
repeated_failure = 0.0

# EWMA parameters
alpha_short = 0.4      # t1 window
alpha_session = 0.08   # t5 window
alpha_baseline = 0.02  # t15 window

# Transition thresholds
tighten_threshold_t1 = 0.3
tighten_threshold_t5 = 0.5
loosening_threshold_t1 = 0.9
loosening_threshold_t5 = 0.8
loosening_window_turns = 20

[ratchet]
min_frequency = 5
min_sessions = 3
min_success_rate = 0.8
lookback_days = 30
# Heed gate for nudged tool promotions (kibitzer A/B evidence)
min_nudge_trials = 5
min_heed_rate = 0.25
min_heed_lift = 0.0

[sandbox]
# blq integration (optional)
enabled = true

[metrics]
default_period_days = 30

[briefing]
lookback_days = 14
top_tools = 5

[store]
path = ".riggs/store.duckdb"
```

## Design Principles

### Reads Everything, Writes Nothing (to other tools)
Riggs is a **read-only observer** of the Rigged tool suite. It ingests state from kibitzer, blq, jetsam, and fledgling but never mutates their configs or data directly. Promotions are written to `.riggs/` only, then reviewed by humans before application.

### Human in the Loop, Gate at the Boundary
Promotion decisions require human review and approval, and mode control stays with kibitzer. What riggs itself guarantees is the **fail-closed trust gate**: capability-expanding actions (tool promotions, LOOSEN recommendations, `agent-riggs gate` consumers) are denied unless verified trust history supports them. Constraint tightening is suggested, never gated.

### Specified Throughout
Every threshold, weight, and heuristic is configurable in `.riggs/config.toml`. Defaults are sensible but tunable.

### DuckDB Native
No external database or daemon. Schema is declared per-plugin as idempotent DDL. Queries use standard SQL. Data is portable and inspectable.

### Graceful Degradation
Optional tools (blq, jetsam, fledgling) are discovered at runtime. If absent, Riggs continues with reduced capability — sandbox features disabled, commit patterns skipped, etc.

## Design Specification

For detailed architecture, event types, trust formulas, failure categorization, and ratchet logic, see:

**[Agent Riggs Design Spec](docs/superpowers/specs/2026-03-29-agent-riggs-design.md)**

For step-by-step implementation plan and build order, see:

**[Agent Riggs Implementation Plan](docs/superpowers/plans/2026-03-29-agent-riggs.md)**

## Dependencies

| Package | Role | Required |
|---|---|---|
| click | CLI framework | Yes |
| duckdb | Persistence | Yes |
| mcp[cli] | MCP server | Yes |
| tomli-w | Config serialization | Yes |
| kibitzer | Event source | Optional |
| blq | Sandbox integration | Optional |
| jetsam | Commit pattern analysis | Optional |
| fledgling | Conversation analytics | Optional |

Python 3.11+ required (for `tomllib` stdlib and clean union syntax).

## License

MIT

## Related Tools

- **[kibitzer](https://github.com/anthropics/rigged)** — In-session control and constraint management
- **[blq](https://github.com/anthropics/rigged)** — Sandboxing and resource profiling
- **[jetsam](https://github.com/anthropics/rigged)** — File state and git integration
- **[fledgling](https://github.com/anthropics/rigged)** — Conversation and context analytics
