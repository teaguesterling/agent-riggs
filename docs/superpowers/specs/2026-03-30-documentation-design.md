# Agent Riggs Documentation Design Spec

## Goal

Create user-facing documentation: a narrative tutorial and reference docs for configuration, CLI, integration, architecture, and MCP.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Format | Plain markdown in `docs/` | Readable on GitHub, no build tooling needed. Can add mkdocs later. |
| Structure | Tutorial + 5 reference docs + index | Tutorial teaches workflow, reference docs are what you come back to. |
| Simulated data | Yes, in tutorial | User has no accumulated sessions yet. Manual `.kibitzer/` data lets every command produce real output. |

## Files

```
docs/
├── index.md              # Landing page with links
├── tutorial.md           # Narrative walkthrough
├── the-ratchet.md        # How the system evolves over time
├── configuration.md      # Every config.toml field
├── cli-reference.md      # Every command with examples
├── integration.md        # How Riggs connects to sibling tools (incl. lackpy)
├── architecture.md       # Plugin system, data flow, schema
└── mcp.md                # MCP resources and tools
```

## index.md

Short landing page. One paragraph describing what agent-riggs does, then a list of links:
- **Tutorial** — Start here. Walk through setup, ingestion, trust scores, ratchet, and metrics.
- **CLI Reference** — Every command, every flag, example output.
- **Configuration** — Complete config.toml reference.
- **Integration** — How Riggs connects to kibitzer, lackpy, blq, jetsam, fledgling.
- **Architecture** — Plugin system, data flow, DuckDB schema, design principles.
- **MCP Server** — Resources and tools for agent access.
- **The Ratchet** — How the system evolves: trust informs transitions, patterns become templates, failed delegations become new tools.

## tutorial.md

Narrative walkthrough. Each section shows exact commands and output, then explains.

### Sections

1. **Install & Init** — `pip install agent-riggs`, `agent-riggs init`, what `.riggs/` contains (config.toml, store.duckdb), tool discovery output.

2. **Simulating a Session** — Create `.kibitzer/state.json` with session_id, mode, turn_count. Create `.kibitzer/intercept.log` with JSONL entries: 3 successful Read calls, 1 Bash with a suggestion (suboptimal), 1 failed Edit (old_string not found). Show exact file contents.

3. **Ingesting** — `agent-riggs ingest`. Show output. Explain: Riggs read kibitzer's state and intercept log, classified each event, scored it, computed EWMA, stored everything in DuckDB.

4. **Reading Trust Scores** — `agent-riggs status` and `agent-riggs trust current`. Explain the three numbers: t1 (now, ~5 turn half-life), t5 (session, ~25 turns), t15 (baseline, ~100 turns). "Like uptime."

5. **Understanding EWMA** — Brief explanation of exponentially weighted moving averages. How alpha controls responsiveness. Why three windows: short catches immediate problems, session tracks the current trajectory, baseline is what's normal for this project.

6. **Adding More Sessions** — Modify the kibitzer data to simulate a second session with more failures. Ingest again. Show trust scores dropping. Show `agent-riggs trust history`.

7. **Trust Transitions** — Explain the threshold rules. When trust_1 < 0.3: recommend tightening. When both low: auto-tighten. How Riggs writes recommendations to `.kibitzer/state.json` for kibitzer to pick up. Show the relationship.

8. **Ratchet Candidates** — After enough sessions, `agent-riggs ratchet candidates` shows patterns. Explain tool promotion candidates (bash patterns with structured alternatives) and constraint candidates (repeated failures at boundaries).

9. **Promoting and Rejecting** — `agent-riggs ratchet promote <key>`, `agent-riggs ratchet reject <key> --reason "..."`. Show `agent-riggs ratchet history`. Explain: promotions change sibling tool configs, rejections are tracked for re-evaluation.

10. **Metrics Dashboard** — `agent-riggs metrics`. Walk through each metric: ratchet velocity, self-service ratio, computation channel fraction, trust trajectory, failure rate, mode distribution.

11. **Session Briefing** — `agent-riggs brief`. When to use it: start of a new session, after being away. What it tells you: trust baseline, last session summary, known issues, active candidates.

12. **MCP Server** — How to access Riggs data from within a Claude Code session. The `riggs://` resources. The agent-callable tools. Read-only by design.

13. **The Ratchet in Action** — Connect the dots: how the session data you just generated would, over time, produce ratchet candidates. How a lackpy template promotion works. How a tool gap gets identified. Point to `the-ratchet.md` for the full picture.

14. **What's Next** — Tuning thresholds in config.toml. Installing the full suite. Integrating with lackpy for delegation traces. Using MotherDuck for sharing.

## configuration.md

One table per TOML section.

### [trust]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| score_success | float | 1.0 | Score for a successful tool call in correct mode |
| score_suboptimal | float | 0.7 | Score for successful call with a structured alternative available |
| ... | | | |
| alpha_short | float | 0.4 | Decay rate for t1 (short window, ~5 turn half-life) |
| alpha_session | float | 0.08 | Decay rate for t5 (session window, ~25 turn half-life) |
| alpha_baseline | float | 0.02 | Decay rate for t15 (baseline window, ~100 turn half-life) |
| tighten_threshold | float | 0.3 | t1 below this triggers tightening recommendation |
| auto_tighten_threshold | float | 0.5 | t5 below this (combined with low t1) triggers auto-tighten |
| loosen_threshold | float | 0.9 | t1 above this may trigger loosening suggestion |
| loosen_sustained_turns | int | 20 | Turns of sustained high trust before suggesting loosening |

### [ratchet]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| min_frequency | int | 5 | Minimum occurrences for a candidate |
| min_sessions | int | 3 | Minimum distinct sessions for a candidate |
| min_success_rate | float | 0.8 | Minimum success rate for tool promotion candidates |
| lookback_days | int | 30 | Time window for candidate identification |

### [sandbox]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| memory_headroom | float | 2.0 | Multiplier for memory limit recommendations |
| timeout_headroom | float | 3.0 | Multiplier for timeout limit recommendations |
| cpu_headroom | float | 2.0 | Multiplier for CPU limit recommendations |
| min_runs_for_tightening | int | 5 | Minimum runs before recommending tightening |

### [metrics]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| default_period_days | int | 30 | Default analysis window for metrics |

### [store]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| path | string | ".riggs/store.duckdb" | Path to the DuckDB database file |

## cli-reference.md

One section per command with: synopsis, description, options, example.

Commands: init, ingest, status, trust current, trust history, ratchet candidates, ratchet promote, ratchet reject, ratchet history, metrics, brief.

Each with exact example output (matching what the tutorial shows or what `--help` describes).

## integration.md

Per-tool section:

### Kibitzer
- **Reads:** `.kibitzer/state.json` (mode, session_id, turn_count), `.kibitzer/intercept.log` (JSONL)
- **Writes:** Recommendations to `.kibitzer/state.json` (trust-informed transitions)
- **When absent:** Core ingest source. Without kibitzer, Riggs has no primary data source.

### blq
- **Reads:** `.lq/blq.duckdb` (sandbox profiles, run history)
- **Writes:** Nothing. Sandbox tightening delegates to `blq sandbox tighten` via CLI.
- **When absent:** Sandbox plugin not registered. Everything else works.

### Jetsam
- **Reads:** `.jetsam/` state files (commit patterns, plan tracking)
- **Writes:** Nothing.
- **When absent:** Commit pattern analysis unavailable. Everything else works.

### lackpy
- **Reads:** Execution traces from lackpy delegations (program, kit, grade, generation_tier, tool calls, success/failure, duration)
- **Writes:** Template registrations — when agent-riggs promotes a pattern, it registers it as a lackpy Tier 0 template so future identical intents skip model inference entirely.
- **Ratchet role:** Three distinct feedback loops:
  1. **Trace audit** — every lackpy execution produces a structured trace that feeds the trust engine and failure stream. Generation tier (template vs rules vs ollama vs anthropic) directly measures computation channel fraction.
  2. **Template promotion** — frequent, successful delegation patterns graduate from model inference to deterministic templates. This IS the ratchet turning — the system gets faster and cheaper over time.
  3. **Tool gap identification** — repeated delegation failures in a domain are a demand signal. Agent-riggs surfaces these as a new candidate type: "lackpy needs a tool for X." This is how the tool ecosystem grows.
- **When absent:** Delegation trace analysis unavailable. Template promotion disabled. Trust and ratchet still work from other sources.

### Fledgling
- **Reads:** Fledgling access log (conversation analytics, tool usage)
- **Writes:** Nothing.
- **When absent:** Conversation analytics unavailable. Everything else works.

## the-ratchet.md

The conceptual centerpiece — explains how the entire system evolves over time. This is the document that makes agent-riggs make sense as more than a metrics dashboard.

### Sections

1. **What is the ratchet?** — The system only tightens. Patterns that work get crystallized. Boundaries that get violated get reinforced. Tools that are needed get created. The human decides when and what, but the system identifies the candidates.

2. **Three feedback loops**

   **Loop 1: Trust-informed transitions** (within a session)
   - Agent behavior → trust score → EWMA → transition recommendation → kibitzer acts
   - Timescale: per-turn. Takes effect immediately.
   - Example: 5 consecutive failures → trust_1 drops below 0.3 → Riggs recommends tightening → kibitzer switches to debug mode.

   **Loop 2: Pattern promotion** (across sessions)
   - Bash commands / lackpy delegations → frequency + success tracking → ratchet candidate → human promotes → config change or template registration
   - Timescale: days/weeks. Takes effect next session.
   - Two sub-types:
     - **Tool promotion**: `grep -rn 'def '` used 89 times across 23 sessions → promote fledgling interceptor from observe to suggest
     - **Template promotion**: `lackpy delegate "find callers of X"` succeeds 47 times → register as Tier 0 template, skip model inference forever

   **Loop 3: Tool gap identification** (across sessions)
   - Repeated delegation failures in a domain → "lackpy needs a tool for X" → human creates or installs tool → gap closes
   - Timescale: weeks/months. Changes the tool ecosystem itself.
   - Example: lackpy repeatedly fails to fulfill "check test coverage for module X" → agent-riggs surfaces: "delegation_failure in coverage domain, 12 failures across 8 sessions" → human adds a coverage tool to lackpy's toolbox.

3. **The ratchet across the suite** — Table showing each tool, what ratchet fuel it produces, what ratchet turn it enables (from the README spec).

4. **Measuring the ratchet** — How to read `agent-riggs metrics` to see if the ratchet is turning:
   - Self-service ratio going up = structured tools replacing bash
   - Computation channel fraction going down = templates replacing model calls
   - Debug mode percentage going down = fewer sessions going wrong
   - Ratchet velocity = promotions per month

5. **When the ratchet doesn't turn** — What it means when metrics plateau. When to review configuration. When the issue is the tool ecosystem, not the agent.

## architecture.md

### Plugin System
ServicePlugin protocol. How plugins register CLI commands, MCP resources/tools, and schema DDL. Assembly discovers and registers plugins.

### Service Layer
RiggsService composes plugins. CLI and MCP server are thin shells. read_only flag controls mutability.

### Data Flow
During session: tools write their own state. Between sessions: `agent-riggs ingest` pulls from all sources. Store accumulates across sessions.

### DuckDB Schema
All tables: turns, failure_stream, session_summaries (trust plugin), ratchet_decisions (ratchet plugin), sandbox_profiles (sandbox plugin).

### Design Principles
1. Reads everything, writes nothing (to other tools)
2. Human in the loop for promotions
3. Specified throughout (no LLM in analysis loop)
4. DuckDB native
5. Graceful degradation

## mcp.md

### Resources

| URI | Description |
|-----|-------------|
| riggs://briefing | Session briefing markdown |
| riggs://trust | Current trust scores and trajectory |
| riggs://ratchet | Pending candidates and recent decisions |
| riggs://sandbox | Sandbox grades and recommendations |
| riggs://metrics | Ratchet metrics |

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| RiggsTrust | window? (int) | Trust scores, optionally with history |
| RiggsMetrics | period? (int) | Ratchet metrics for a time period |
| RiggsFailures | category? (str), limit? (int) | Query failure stream |
| RiggsSandbox | command? (str) | Sandbox grades and recommendations |

All read-only. MCP server opens store in read_only=True mode.
