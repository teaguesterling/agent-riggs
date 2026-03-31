# Agent Riggs Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create user-facing documentation — a narrative tutorial, a conceptual guide to the ratchet, and reference docs for configuration, CLI, integration, architecture, and MCP.

**Architecture:** Plain markdown files in `docs/`. No build tooling. Each file is self-contained and readable on GitHub.

**Tech Stack:** Markdown

**Spec:** `docs/superpowers/specs/2026-03-30-documentation-design.md`

---

## Files to create

```
docs/
├── index.md              # Landing page
├── tutorial.md           # Narrative walkthrough (~14 sections)
├── the-ratchet.md        # Three feedback loops, measuring the ratchet
├── configuration.md      # Every config.toml field
├── cli-reference.md      # Every command with examples
├── integration.md        # Kibitzer, lackpy, blq, jetsam, fledgling
├── architecture.md       # Plugin system, data flow, schema, principles
└── mcp.md                # Resources and tools
```

---

### Task 1: Index Page

**Files:**
- Create: `docs/index.md`

- [ ] **Step 1: Write docs/index.md**

```markdown
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
```

- [ ] **Step 2: Verify the file renders correctly**

Run: `head -20 docs/index.md`
Expected: See the title and guide links

- [ ] **Step 3: Commit**

```bash
git add docs/index.md
git commit -m "docs: add index page"
```

---

### Task 2: Tutorial (Part 1 — Setup and First Ingest)

**Files:**
- Create: `docs/tutorial.md`

This is the largest doc. We'll write it in two tasks to keep things manageable.

- [ ] **Step 1: Write tutorial.md sections 1-7**

```markdown
# Tutorial: Getting Started with Agent Riggs

This tutorial walks you through agent-riggs from first install to reading metrics across sessions. Every command is shown with real output — you can follow along on any project.

## 1. Install and Initialize

```bash
pip install agent-riggs
```

Navigate to your project directory and initialize:

```bash
cd your-project/
agent-riggs init
```

Output:
```
Initialized .riggs/ in /home/you/your-project
Discovered tools: kibitzer
No sibling tools discovered yet.
```

What happened:
- Created `.riggs/` directory
- Copied default `config.toml` (you can customize this later — see [Configuration](configuration.md))
- Created `store.duckdb` — a DuckDB database that accumulates data across sessions
- Checked for sibling tools (kibitzer, blq, jetsam, fledgling) by looking for their config directories and PATH entries

The `.riggs/` directory should be in your `.gitignore` — the store is local state, not project configuration.

## 2. Simulating a Session

In normal use, kibitzer writes session data automatically during a Claude Code session. For this tutorial, we'll create the data by hand so you can see exactly what Riggs reads.

Create `.kibitzer/state.json`:

```json
{
  "mode": "implement",
  "session_id": "sess-tutorial-1",
  "turn_count": 5
}
```

Create `.kibitzer/intercept.log` with one JSON object per line:

```jsonl
{"timestamp": "2026-03-30T10:00:00Z", "tool": "Read", "success": true}
{"timestamp": "2026-03-30T10:01:00Z", "tool": "Read", "success": true}
{"timestamp": "2026-03-30T10:02:00Z", "tool": "Read", "success": true}
{"timestamp": "2026-03-30T10:03:00Z", "tool": "Bash", "command": "grep -rn 'def validate' src/", "success": true, "suggestion": "Use FindDefinitions (fledgling)"}
{"timestamp": "2026-03-30T10:04:00Z", "tool": "Edit", "success": false, "error": "old_string not found in file"}
```

This simulates a 5-turn session where:
- Turns 1-3: Agent reads files successfully (score: 1.0 each)
- Turn 4: Agent uses `grep` when fledgling's FindDefinitions was available (score: 0.7 — suboptimal)
- Turn 5: An edit fails because `old_string` didn't match (score: 0.2 — failure)

## 3. Ingesting the Session

```bash
agent-riggs ingest
```

Output:
```
Ingested 5 turns from ['kibitzer']
Recorded 1 failures
```

What happened under the hood:
1. Riggs discovered kibitzer's state files (`.kibitzer/state.json` and `.kibitzer/intercept.log`)
2. Parsed each intercept log entry into a **TurnEvent** with a category (success, suboptimal, failure, etc.)
3. **Scored** each event according to `.riggs/config.toml` weights
4. Updated the **three-window EWMA** (exponentially weighted moving average) after each score
5. Stored every turn in the `turns` table and failures in the `failure_stream` table in DuckDB

## 4. Reading Trust Scores

The quick view:

```bash
agent-riggs status
```

```
trust: 0.61 / 0.91 / 0.98
       now    session  baseline
```

Three numbers, like `uptime`. The detailed view:

```bash
agent-riggs trust current
```

```
trust_1 (now):      0.6080
trust_5 (session):  0.9139
trust_15 (baseline):0.9781
```

What do these mean?

| Window | Value | What it tells you |
|--------|-------|-------------------|
| **trust_1** (now) | 0.61 | The agent is in mild trouble *right now*. The last two turns were suboptimal (0.7) and a failure (0.2), dragging this down. |
| **trust_5** (session) | 0.91 | This session is going fine overall. Five turns isn't enough to move the session window much. |
| **trust_15** (baseline) | 0.98 | This project is healthy. Only one session of data, almost no impact on the long-term baseline. |

The trust_1 value of 0.61 tells you: the agent stumbled at the end, but it's not in crisis. If trust_1 drops below 0.3, Riggs will recommend tightening the mode (see section 7).

## 5. Understanding EWMA

The trust score uses an **exponentially weighted moving average** — the same math behind the `load average` numbers in Unix's `uptime` command.

Each window has an **alpha** (decay rate) that controls how responsive it is:

| Window | Alpha | Half-life | Responsiveness |
|--------|-------|-----------|----------------|
| trust_1 | 0.4 | ~5 turns | Reacts fast. Shows what's happening now. |
| trust_5 | 0.08 | ~25 turns | Smooths over bumps. Shows the session trajectory. |
| trust_15 | 0.02 | ~100 turns | Very stable. Shows what's normal for this project. |

The update formula is simple: `new = old * (1 - alpha) + score * alpha`

After a perfect turn (score 1.0), trust stays where it is. After a failure (score 0.2), trust_1 drops fast, trust_5 dips slightly, trust_15 barely moves. Recovery is the same — trust_1 bounces back in a few good turns, trust_15 takes many sessions.

This is why three windows matter: trust_1 catches immediate problems, trust_5 tracks whether the session is trending up or down, and trust_15 tells you if a project is systematically healthy or sick.

## 6. Adding More Sessions

Let's simulate a second session — this one goes badly. Replace the kibitzer files:

`.kibitzer/state.json`:
```json
{
  "mode": "debug",
  "session_id": "sess-tutorial-2",
  "turn_count": 4
}
```

`.kibitzer/intercept.log`:
```jsonl
{"timestamp": "2026-03-30T14:00:00Z", "tool": "Edit", "success": false, "error": "old_string not found in file"}
{"timestamp": "2026-03-30T14:01:00Z", "tool": "Edit", "success": false, "error": "old_string not found in file"}
{"timestamp": "2026-03-30T14:02:00Z", "tool": "Bash", "command": "grep -rn 'class Parser' src/", "success": true, "suggestion": "Use FindDefinitions (fledgling)"}
{"timestamp": "2026-03-30T14:03:00Z", "tool": "Edit", "success": false, "error": "old_string not found in file"}
```

Ingest:
```bash
agent-riggs ingest
```

```
Ingested 4 turns from ['kibitzer']
Recorded 3 failures
```

Now check trust:
```bash
agent-riggs status
```

```
trust: 0.24 / 0.86 / 0.96
       now    session  baseline
```

trust_1 has dropped to 0.24 — below the tighten threshold of 0.3. This is the signal that the agent is struggling.

Check the history:
```bash
agent-riggs trust history --limit 5
```

This shows the trust trajectory across both sessions — you can see exactly when things went wrong.

## 7. Trust-Informed Transitions

When trust drops below configured thresholds, Riggs generates recommendations:

| Condition | Action |
|-----------|--------|
| trust_1 < 0.3 | Recommend mode tightening to kibitzer |
| trust_1 < 0.3 AND trust_5 < 0.5 | Auto-tighten (kibitzer acts immediately) |
| trust_5 declining for 10+ turns | Coach: "approach may not be working" |
| trust_1 > 0.9 AND trust_5 > 0.8 for 20+ turns | Suggest loosening |
| trust_15 < 0.5 | Flag: "project configuration needs review" |

In our second session, trust_1 hit 0.24 — below the tighten threshold. If kibitzer were running, Riggs would write a recommendation to `.kibitzer/state.json`, and kibitzer's mode controller would pick it up.

This is how Riggs and kibitzer work together: Riggs observes across sessions and recommends. Kibitzer acts within the session. Riggs never enforces directly — it informs kibitzer's rules.

All thresholds are configurable in `.riggs/config.toml` under `[trust]`. See [Configuration](configuration.md) for details.
```

- [ ] **Step 2: Verify the file renders**

Run: `wc -l docs/tutorial.md`
Expected: ~150-170 lines

- [ ] **Step 3: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: tutorial part 1 — setup through trust transitions"
```

---

### Task 3: Tutorial (Part 2 — Ratchet, Metrics, Briefing, MCP)

**Files:**
- Modify: `docs/tutorial.md` (append sections 8-14)

- [ ] **Step 1: Append sections 8-14 to tutorial.md**

Append the following after section 7:

```markdown

## 8. Ratchet Candidates

After enough sessions accumulate, `agent-riggs ratchet candidates` identifies patterns that recur across sessions. There are two types:

**Tool promotion candidates** — Bash patterns that have a structured alternative:

```
agent-riggs ratchet candidates
```

```
  [tool_promotion] bash-to-finddefinitions
    Graduate FindDefinitions interceptor
    Evidence: {'frequency': 89, 'sessions': 23, 'success_rate': 0.97}

  [tool_promotion] bash-to-blq-run-test
    Graduate blq run test interceptor
    Evidence: {'frequency': 134, 'sessions': 41, 'success_rate': 0.91}
```

These say: "the agent keeps using `grep` for definition searches when fledgling's FindDefinitions exists. It works 97% of the time across 23 sessions. Maybe it's time to nudge the agent toward the structured tool."

**Constraint candidates** — Repeated failures at the same boundary:

```
  [constraint_promotion] edit_failure-Edit-implement
    Repeated edit_failure on Edit in implement mode — review configuration or add documentation
    Evidence: {'occurrences': 28, 'sessions_affected': 15, 'severity': 'systemic'}
```

This says: "the agent keeps trying to edit files and failing with 'old_string not found'. This happens in implement mode across 15 sessions. The agent might need guidance in CLAUDE.md, or the edit approach needs rethinking."

With only our 2 tutorial sessions, you won't see candidates yet — the default thresholds require at least 5 occurrences across 3 sessions. But the pattern is clear: Riggs watches what happens, and when it sees the same thing enough times, it raises its hand.

## 9. Promoting and Rejecting

When a candidate appears and you agree with the recommendation:

```bash
agent-riggs ratchet promote bash-to-finddefinitions --reason "agents should use structured search"
```

What happens:
- The decision is recorded in `ratchet_decisions` with the evidence and your reason
- For tool promotions: the corresponding kibitzer interceptor gets graduated (e.g., from `observe` to `suggest`)
- For lackpy template promotions: the pattern is registered as a Tier 0 template, skipping model inference for future identical intents

If you disagree:

```bash
agent-riggs ratchet reject bash-to-finddefinitions --reason "agents need grep for non-definition searches too"
```

Rejections are tracked. If conditions change (the pattern keeps recurring, the success rate goes up), the candidate can reappear.

View all decisions:

```bash
agent-riggs ratchet history
```

Every promotion and rejection is recorded with timestamp, evidence, and reason — a complete audit trail of how your system evolved.

## 10. Metrics Dashboard

```bash
agent-riggs metrics
```

```
RATCHET METRICS (0 sessions)

  Ratchet velocity:        0 promotions
  Self-service ratio:      0% structured
  Computation channel %:   0%
  Trust trajectory:        1.00 -> 0.91
  Failure rate:            0%

  Mode distribution:
    implement: 100%
```

What each metric means:

| Metric | What it measures | Good direction |
|--------|-----------------|----------------|
| **Ratchet velocity** | Promotions per period | Up (system is evolving) |
| **Self-service ratio** | Fraction of tool calls using structured tools vs bash | Up |
| **Computation channel %** | Fraction of calls at computation level 4+ (model inference) | Down |
| **Trust trajectory** | trust_5 at start vs end of period | Improving (going up) |
| **Failure rate** | Failures / total turns | Down |
| **Mode distribution** | Time spent in each mode | Less debug, more implement |

Over time, you want to see: self-service ratio climbing, computation channel fraction declining, debug mode percentage shrinking. That's the ratchet turning — the system is getting better at using structured tools and spending less time in crisis.

Use `--period` to change the analysis window:

```bash
agent-riggs metrics --period 7    # last 7 days
agent-riggs metrics --period 90   # last quarter
```

## 11. Session Briefing

When you start a new session or come back after being away:

```bash
agent-riggs brief
```

```
PROJECT BRIEFING: your-project

Trust baseline: 0.98
Last session: sess-tutorial-2, 4 turns, trust 0.24
Known issues:
  - failure (4 occurrences)
Active ratchet candidates: 0
```

The briefing composes data from trust, ratchet, and metrics into a quick summary. It's also available as an MCP resource (`riggs://briefing`) that can be included in the system prompt automatically.

## 12. MCP Server

When the Riggs MCP server is running, agents can access trust data and metrics during a session without CLI calls.

**Resources** (always available, included in context):

| URI | What it provides |
|-----|-----------------|
| `riggs://briefing` | Session briefing (trust baseline, last session, known issues) |
| `riggs://trust` | Current trust scores |
| `riggs://ratchet` | Pending candidates and recent decisions |
| `riggs://metrics` | Ratchet metrics |
| `riggs://sandbox` | Sandbox grades (when blq is available) |

**Tools** (agent-callable):

| Tool | What it does |
|------|-------------|
| `RiggsTrust(window?)` | Get trust scores, optionally with history |
| `RiggsMetrics(period?)` | Get metrics for a time period |
| `RiggsFailures(category?, limit?)` | Query the failure stream |
| `RiggsSandbox(command?)` | Get sandbox grades |

All read-only. The MCP server opens the store in read-only mode — agents can observe but never modify Riggs data. All mutations happen through the CLI (human in the loop).

See [MCP Reference](mcp.md) for full details.

## 13. The Ratchet in Action

Step back and look at what you've seen:

1. **Trust scores** tracked the agent's behavior per-turn, catching problems in real time
2. **Failure stream** accumulated across sessions, revealing patterns no single session could show
3. **Ratchet candidates** would have surfaced those patterns as actionable recommendations
4. **Promotions** would have changed how the tools work — tighter interceptors, new templates, better constraints

This is the ratchet: the system only gets tighter. Patterns that work get crystallized. Boundaries that get violated get reinforced. Tools that are missing get identified.

And when lackpy is in the picture, the ratchet gets another dimension:
- **Successful delegations** become templates — the model gets called less over time
- **Failed delegations** reveal gaps — "lackpy needs a tool for X" becomes a new kind of candidate
- **Generation tier** tracks the shift — you can measure templates replacing model calls in the metrics

For the full picture, see [The Ratchet](the-ratchet.md).

## 14. What's Next

**Tune thresholds.** The defaults work well for most projects, but every codebase is different. If trust_1 triggers tightening too aggressively, raise `tighten_threshold`. If candidates appear too slowly, lower `min_frequency`. See [Configuration](configuration.md).

**Install the full suite.** Agent-riggs works best with the complete Rigged tool suite:

```bash
pip install agent-riggs[full]  # kibitzer + fledgling + blq + jetsam
agent-riggs init --full
```

**Integrate with lackpy.** When lackpy is installed, Riggs can ingest execution traces for trust scoring and ratchet analysis. Template promotions skip model inference for patterns that have proven reliable.

**Query the store directly.** The `.riggs/store.duckdb` file is a standard DuckDB database. You can query it with any DuckDB client:

```sql
SELECT failure_category, count(*)
FROM failure_stream
WHERE project = 'your-project'
GROUP BY failure_category
ORDER BY count(*) DESC;
```
```

- [ ] **Step 2: Verify the complete tutorial**

Run: `wc -l docs/tutorial.md`
Expected: ~300-350 lines total

Run: `grep '^## ' docs/tutorial.md | wc -l`
Expected: 14 (sections 1-14)

- [ ] **Step 3: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: tutorial part 2 — ratchet, metrics, briefing, MCP, what's next"
```

---

### Task 4: The Ratchet

**Files:**
- Create: `docs/the-ratchet.md`

- [ ] **Step 1: Write the-ratchet.md**

```markdown
# The Ratchet

Agent Riggs exists to turn the ratchet. Everything else — trust scores, failure streams, metrics — is mechanism in service of one idea: **the system should get better over time, and it should never silently get worse.**

## What is the ratchet?

The ratchet is a one-way mechanism. Patterns that work get crystallized. Boundaries that get violated get reinforced. Tools that are needed get created. The system only tightens — it never loosens without a human deciding to.

The human decides *when* and *what*. The system identifies *candidates*. This is the fundamental contract: Riggs surfaces evidence, you make decisions, and every decision is recorded for audit.

## Three Feedback Loops

The ratchet operates through three loops at different timescales.

### Loop 1: Trust-Informed Transitions

**Timescale:** Per-turn. Takes effect immediately.

```
Agent behavior → trust score → EWMA → transition recommendation → kibitzer acts
```

This is the fastest loop. Every tool call gets a trust score (0-1). Three exponentially weighted moving averages track what's happening now (trust_1), this session (trust_5), and this project's baseline (trust_15).

When trust drops below thresholds, Riggs recommends action:

| Condition | Recommendation |
|-----------|---------------|
| trust_1 < 0.3 | Tighten mode |
| trust_1 < 0.3 AND trust_5 < 0.5 | Auto-tighten |
| trust_5 declining 10+ turns | "Approach may not be working" |
| trust_1 > 0.9, trust_5 > 0.8 for 20+ turns | Suggest loosening |
| trust_15 < 0.5 | "Project configuration needs review" |

Riggs recommends. Kibitzer acts. Riggs never enforces directly.

**Example:** The agent makes 5 consecutive failed edits. trust_1 drops to 0.18. Riggs writes a tighten recommendation to `.kibitzer/state.json`. Kibitzer's mode controller switches from `implement` to `debug`. The agent is now constrained to read-only tools until it can demonstrate it understands the problem.

### Loop 2: Pattern Promotion

**Timescale:** Days to weeks. Takes effect next session.

```
Repeated patterns → frequency tracking → ratchet candidate → human promotes → config/template change
```

This loop watches what agents *do* across sessions and identifies patterns worth crystallizing.

**Tool promotion.** The agent uses `grep -rn 'def validate' src/` 89 times across 23 sessions with a 97% success rate. Fledgling's `FindDefinitions` does the same thing but produces structured output. Riggs surfaces this as a tool promotion candidate. You promote it, and kibitzer's interceptor graduates from `observe` to `suggest` — now the agent gets a nudge toward the structured tool.

**Template promotion.** lackpy's `delegate("find callers of validate_token")` succeeds 47 times across 30 sessions. The generated program is always the same. Riggs surfaces this as a template candidate. You promote it, and the pattern is registered as a Tier 0 template in lackpy. Future identical intents skip model inference entirely — they resolve in microseconds instead of seconds, at zero cost.

This is the computation channel narrowing: work that once required a model call gets crystallized into a deterministic lookup. You can measure this shift in `agent-riggs metrics` as the computation channel fraction declining over time.

### Loop 3: Tool Gap Identification

**Timescale:** Weeks to months. Changes the tool ecosystem itself.

```
Repeated delegation failures → demand signal → "lackpy needs a tool for X" → human creates tool → gap closes
```

This is the deepest loop. When lackpy repeatedly fails to fulfill intents in a particular domain, that's not just a quality problem — it's a **demand signal for a new tool**.

**Example:** Agents keep asking lackpy to "check test coverage for module X". The delegation fails every time because there's no coverage tool in lackpy's toolbox. After 12 failures across 8 sessions, Riggs surfaces: `delegation_failure in coverage domain — consider adding a coverage tool`.

You install or create a coverage tool, add it to lackpy's toolbox, and the gap closes. Future coverage queries succeed, generate successful traces, and eventually become templates (Loop 2).

This is how the tool ecosystem grows: not by speculative design, but by observed demand.

## The Ratchet Across the Suite

Each tool in the Rigged suite contributes fuel to the ratchet:

| Tool | Ratchet fuel it produces | Ratchet turn it enables |
|------|--------------------------|-------------------------|
| **Kibitzer** | Per-session failure stream, interceptor logs, coach observations | Interceptor graduation (observe → suggest → redirect) |
| **lackpy** | Execution traces, generation tier, delegation outcomes | Template promotion, tool gap identification |
| **blq** | Run history, sandbox profiles, resource metrics | Sandbox tightening, command registration |
| **Fledgling** | Conversation analytics, tool usage patterns | Macro creation, query promotion |
| **Jetsam** | Commit patterns, plan tracking | Workflow crystallization |
| **Agent Riggs** | Cross-session aggregation of all the above | Promotion decisions, configuration recommendations |

## Measuring the Ratchet

Run `agent-riggs metrics` and look for these signals:

| Metric | What it tells you | The ratchet is turning when... |
|--------|-------------------|-------------------------------|
| **Self-service ratio** | Structured tools vs bash | Going up — agents use structured tools more |
| **Computation channel %** | Model calls vs templates/rules | Going down — templates replace model calls |
| **Debug mode %** | Time spent in crisis | Going down — fewer sessions go wrong |
| **Ratchet velocity** | Promotions per month | Steady — you're making decisions regularly |
| **Trust trajectory** | Baseline trust trend | Improving — projects are getting healthier |
| **Failure rate** | Failures per turn | Declining — fewer things go wrong |

## When the Ratchet Doesn't Turn

If metrics plateau, ask:

**Are candidates appearing but not being promoted?** Run `agent-riggs ratchet candidates`. If there are pending candidates, review them. The ratchet needs human decisions to turn.

**Are no candidates appearing?** The thresholds might be too high. Lower `min_frequency` or `min_sessions` in `.riggs/config.toml`. Or there genuinely isn't enough data yet — the ratchet needs multiple sessions to identify patterns.

**Is the failure rate flat despite promotions?** The failures might not be tool-related. Look at the failure categories — if they're mostly `edit_failure`, the issue is the agent's approach to editing, not the tool ecosystem. Consider adding guidance to CLAUDE.md rather than promoting tools.

**Is the self-service ratio flat?** The structured alternatives might not be good enough. If agents keep choosing bash over fledgling, maybe fledgling's output isn't what they need. The ratchet identifies *what's happening*, but the fix might be improving the tools, not just promoting them.

The ratchet is a feedback mechanism, not an autopilot. It shows you where the system is and suggests where it should go. You steer.
```

- [ ] **Step 2: Verify**

Run: `grep '^## ' docs/the-ratchet.md | wc -l`
Expected: 6 sections

- [ ] **Step 3: Commit**

```bash
git add docs/the-ratchet.md
git commit -m "docs: the ratchet — three feedback loops and how to measure them"
```

---

### Task 5: Configuration Reference

**Files:**
- Create: `docs/configuration.md`

- [ ] **Step 1: Write configuration.md**

```markdown
# Configuration Reference

Agent Riggs is configured through `.riggs/config.toml`. When you run `agent-riggs init`, a copy of the defaults is placed in your project. Any value you set overrides the default; values you omit keep their defaults.

## [trust]

Trust scoring weights and EWMA parameters.

### Scoring Weights

Each turn event gets a score between 0 and 1. These weights define the mapping:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `score_success` | float | 1.0 | Successful tool call in the correct mode |
| `score_suboptimal` | float | 0.7 | Successful call, but a structured alternative exists |
| `score_mode_switch_agent` | float | 0.8 | Agent initiated a mode switch (appropriate adaptation) |
| `score_mode_switch_controller` | float | 0.3 | Controller forced a mode switch (System 3 had to intervene) |
| `score_failure` | float | 0.2 | Tool call failed |
| `score_path_denial` | float | 0.1 | Agent tried to write outside mode bounds |
| `score_repeated_failure` | float | 0.0 | Agent is stuck in a failure loop |

### EWMA Parameters

Three exponentially weighted moving averages track trust at different timescales:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `alpha_short` | float | 0.4 | Decay rate for trust_1 (~5 turn half-life). Higher = more responsive. |
| `alpha_session` | float | 0.08 | Decay rate for trust_5 (~25 turn half-life). Tracks session trajectory. |
| `alpha_baseline` | float | 0.02 | Decay rate for trust_15 (~100 turn half-life). Project baseline. |

### Transition Thresholds

When trust crosses these thresholds, Riggs generates recommendations:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tighten_threshold` | float | 0.3 | trust_1 below this triggers a tightening recommendation |
| `auto_tighten_threshold` | float | 0.5 | trust_5 below this (combined with low trust_1) triggers auto-tighten |
| `loosen_threshold` | float | 0.9 | trust_1 above this may trigger a loosening suggestion |
| `loosen_sustained_turns` | int | 20 | Turns of sustained high trust required before suggesting loosening |

## [ratchet]

Controls when ratchet candidates are surfaced.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `min_frequency` | int | 5 | Minimum occurrences of a pattern before it becomes a candidate |
| `min_sessions` | int | 3 | Minimum distinct sessions where the pattern appears |
| `min_success_rate` | float | 0.8 | Minimum success rate for tool promotion candidates |
| `lookback_days` | int | 30 | Time window for candidate identification |

**Tuning guidance:** If you want candidates to appear faster, lower `min_frequency` and `min_sessions`. If you're getting too many noisy candidates, raise them. The `min_success_rate` filters out patterns that work sometimes but fail often — you generally want to keep this high (0.8+).

## [sandbox]

Controls sandbox tightening recommendations. Only active when blq is installed.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `memory_headroom` | float | 2.0 | Multiplier for memory limit recommendations (p95 * this = suggested limit) |
| `timeout_headroom` | float | 3.0 | Multiplier for timeout recommendations |
| `cpu_headroom` | float | 2.0 | Multiplier for CPU limit recommendations |
| `min_runs_for_tightening` | int | 5 | Minimum command runs before recommending tightening |

## [metrics]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_period_days` | int | 30 | Default analysis window for `agent-riggs metrics` |

## [store]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `path` | string | `".riggs/store.duckdb"` | Path to the DuckDB database file (relative to project root) |

## Example: Tuning for a New Project

A new project with few sessions might want faster feedback:

```toml
[ratchet]
min_frequency = 3      # Lower threshold for candidates
min_sessions = 2       # Don't wait for 3 sessions
lookback_days = 14     # Shorter window
```

A mature project with many sessions might want stricter filtering:

```toml
[ratchet]
min_frequency = 10
min_sessions = 5
min_success_rate = 0.9
lookback_days = 60
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/configuration.md
git commit -m "docs: configuration reference with all config.toml fields"
```

---

### Task 6: CLI Reference

**Files:**
- Create: `docs/cli-reference.md`

- [ ] **Step 1: Write cli-reference.md**

```markdown
# CLI Reference

## agent-riggs

```
Usage: agent-riggs [OPTIONS] COMMAND [ARGS]...

  agent-riggs -- cross-session memory and analysis for the Rigged tool suite.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.
```

## Setup Commands

### agent-riggs init

Initialize `.riggs/` directory and DuckDB store.

```bash
agent-riggs init
```

```
Initialized .riggs/ in /home/you/your-project
Discovered tools: kibitzer
```

Creates:
- `.riggs/config.toml` — copy of defaults (only if not present)
- `.riggs/store.duckdb` — DuckDB database with schema for all registered plugins

Discovers sibling tools by checking both PATH (`shutil.which`) and project directories (`.kibitzer/`, `.lq/`, `.jetsam/`, `.fledgling/`).

Safe to run multiple times — idempotent.

### agent-riggs ingest

Pull session data from sibling tool state files into the store.

```bash
agent-riggs ingest
```

```
Ingested 5 turns from ['kibitzer']
Recorded 1 failures
```

Reads from all discovered sources (kibitzer, blq, jetsam, fledgling). Each event is scored and the trust EWMA is updated. Failures are recorded in the failure stream.

## Status Commands

### agent-riggs status

Quick health check — trust scores at a glance.

```bash
agent-riggs status
```

```
trust: 0.61 / 0.91 / 0.98
       now    session  baseline
```

Shows `trust_1 / trust_5 / trust_15`. If no data has been ingested, shows "trust: no data yet".

### agent-riggs brief

Full session briefing.

```bash
agent-riggs brief
```

```
PROJECT BRIEFING: your-project

Trust baseline: 0.98
Last session: sess-tutorial-1, 34 turns, trust 0.91
Known issues:
  - edit_failure (12 occurrences)
Active ratchet candidates: 2
```

## Trust Commands

### agent-riggs trust current

Detailed trust scores.

```bash
agent-riggs trust current
```

```
trust_1 (now):      0.6080
trust_5 (session):  0.9139
trust_15 (baseline):0.9781
```

### agent-riggs trust history

Trust score trajectory over time.

```bash
agent-riggs trust history [--limit N]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--limit` | 20 | Number of entries to show |

```
  [sess-tutorial-2:4] 0.24 / 0.86 / 0.96
  [sess-tutorial-2:3] 0.35 / 0.88 / 0.96
  [sess-tutorial-1:5] 0.61 / 0.91 / 0.98
  ...
```

## Ratchet Commands

### agent-riggs ratchet candidates

Show pending promotion candidates.

```bash
agent-riggs ratchet candidates
```

```
  [tool_promotion] bash-to-finddefinitions
    Graduate FindDefinitions interceptor
    Evidence: {'frequency': 89, 'sessions': 23, 'success_rate': 0.97}
```

Shows nothing if no patterns meet the threshold criteria configured in `[ratchet]`.

### agent-riggs ratchet promote

Promote a candidate. Records the decision and applies the config change.

```bash
agent-riggs ratchet promote <KEY> [--reason TEXT]
```

| Argument/Option | Required | Description |
|-----------------|----------|-------------|
| `KEY` | Yes | The candidate key (e.g., `bash-to-finddefinitions`) |
| `--reason` | No | Why you're promoting this candidate |

### agent-riggs ratchet reject

Reject a candidate with a reason. The rejection is tracked for future re-evaluation.

```bash
agent-riggs ratchet reject <KEY> --reason TEXT
```

| Argument/Option | Required | Description |
|-----------------|----------|-------------|
| `KEY` | Yes | The candidate key |
| `--reason` | Yes | Why you're rejecting (required — document your reasoning) |

### agent-riggs ratchet history

Show all promotion and rejection decisions.

```bash
agent-riggs ratchet history
```

```
  [2026-03-30 14:00:00] promoted: bash-to-finddefinitions — agents should use structured search
  [2026-03-29 10:00:00] rejected: bash-to-blq-run-test — agents need raw pytest output
```

## Metrics Command

### agent-riggs metrics

Ratchet metrics dashboard.

```bash
agent-riggs metrics [--period DAYS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--period` | 30 | Analysis window in days |

```
RATCHET METRICS (47 sessions)

  Ratchet velocity:        3 promotions
  Self-service ratio:      72% structured
  Computation channel %:   31%
  Trust trajectory:        0.87 -> 0.91
  Failure rate:            12%

  Mode distribution:
    implement: 64%
    debug: 18%
    test_dev: 12%
    document: 6%
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/cli-reference.md
git commit -m "docs: CLI reference with all commands and example output"
```

---

### Task 7: Integration Reference

**Files:**
- Create: `docs/integration.md`

- [ ] **Step 1: Write integration.md**

```markdown
# Integration Reference

Agent Riggs reads from sibling tools but never writes to their state. Each tool owns its own storage. Riggs aggregates, analyzes, and recommends. Recommendations flow back through the tools' own configuration mechanisms.

## Kibitzer

**What Riggs reads:**

| File | Content |
|------|---------|
| `.kibitzer/state.json` | Current mode, session ID, turn count |
| `.kibitzer/intercept.log` | JSONL file with one entry per intercepted tool call |

**Intercept log entry format:**

```json
{
  "timestamp": "2026-03-30T10:00:00Z",
  "tool": "Bash",
  "command": "grep -rn 'def validate' src/",
  "success": true,
  "suggestion": "Use FindDefinitions (fledgling)",
  "action": "suggest"
}
```

**Event classification:**

| Log entry pattern | Event category | Trust score |
|-------------------|---------------|-------------|
| `success: true`, no suggestion | success | 1.0 |
| `success: true`, has suggestion | suboptimal | 0.7 |
| `success: false` | failure | 0.2 |
| `success: false`, `error: "old_string not found"` | failure | 0.2 |

**What Riggs writes back:** Trust-informed transition recommendations to `.kibitzer/state.json`. Kibitzer's mode controller reads these and acts on them.

**When absent:** Without kibitzer, Riggs has no primary data source. The trust engine and ratchet work but have nothing to analyze.

## lackpy

**What Riggs reads:** Execution traces from lackpy delegations.

| Trace field | What Riggs uses it for |
|-------------|----------------------|
| `program` | Pattern identification for template candidates |
| `kit` | Tool usage tracking |
| `grade` | Computation level classification |
| `generation_tier` | Computation channel fraction (template vs rules vs model) |
| `entries[].tool` | Per-tool success/failure tracking |
| `entries[].success` | Trust scoring and failure stream |
| `entries[].duration_ms` | Performance profiling |

**Three ratchet roles:**

1. **Trace audit.** Every lackpy execution feeds the trust engine and failure stream. Generation tier (template → rules → ollama → anthropic) directly measures how much model inference the system uses.

2. **Template promotion.** When `agent-riggs ratchet promote` identifies a lackpy delegation pattern, the promotion registers it as a Tier 0 template. Future identical intents skip model inference — they resolve from the template in microseconds, at zero cost.

3. **Tool gap identification.** Repeated delegation failures in a domain surface as a new ratchet candidate type: `delegation_failure`. This is a demand signal — lackpy needs a tool that doesn't exist yet. The human creates or installs the tool, and the gap closes.

**What Riggs writes back:** Template registrations via the lackpy API.

**When absent:** Delegation trace analysis unavailable. Template promotion disabled. Trust and ratchet still work from other sources.

## blq

**What Riggs reads:**

| File | Content |
|------|---------|
| `.lq/blq.duckdb` | Run history, sandbox profiles, resource usage metrics |

**What Riggs does with it:**
- Aggregates execution profiles across sessions (memory, duration, CPU)
- Computes sandbox grades and headroom
- Recommends tightening when resource usage is well below limits

**What Riggs writes back:** Nothing directly. Sandbox tightening delegates to `blq sandbox tighten` via subprocess.

**When absent:** Sandbox plugin not registered. Everything else works normally.

## Jetsam

**What Riggs reads:**

| Location | Content |
|----------|---------|
| `.jetsam/` state files | Commit patterns, plan tracking, workflow history |

**What Riggs does with it:**
- Tracks commit patterns for workflow crystallization candidates
- Monitors plan completion rates

**When absent:** Commit pattern analysis unavailable. Everything else works normally.

## Fledgling

**What Riggs reads:** Fledgling's access log for conversation analytics and tool usage patterns.

**What Riggs does with it:**
- Tracks which code intelligence queries are most common
- Identifies patterns for macro creation candidates

**When absent:** Conversation analytics unavailable. Everything else works normally.

## Data Flow Summary

```
During session:                          Between sessions:

  Claude Code                             agent-riggs ingest
      |                                       |
      +-- kibitzer hooks --> state.json        +-- reads state.json
      +-- lackpy delegate --> traces           +-- reads lackpy traces
      +-- blq run --> .lq/blq.duckdb          +-- reads blq.duckdb
      +-- jetsam --> .jetsam/                  +-- reads .jetsam/
      +-- fledgling --> access log             +-- reads fledgling log
                                               |
                                               v
                                         .riggs/store.duckdb
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/integration.md
git commit -m "docs: integration reference — kibitzer, lackpy, blq, jetsam, fledgling"
```

---

### Task 8: Architecture Reference

**Files:**
- Create: `docs/architecture.md`

- [ ] **Step 1: Write architecture.md**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: architecture reference — plugins, service, schema, principles"
```

---

### Task 9: MCP Reference

**Files:**
- Create: `docs/mcp.md`

- [ ] **Step 1: Write mcp.md**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/mcp.md
git commit -m "docs: MCP server reference — resources, tools, read-only guarantee"
```

---

### Task 10: Final Verification and Link Check

**Files:**
- All docs files

- [ ] **Step 1: Verify all files exist**

Run: `ls -la docs/*.md`
Expected: 8 files: index.md, tutorial.md, the-ratchet.md, configuration.md, cli-reference.md, integration.md, architecture.md, mcp.md

- [ ] **Step 2: Check all internal links resolve**

Run: `grep -oh '\[.*\](.*\.md)' docs/*.md | grep -oP '\(.*?\)' | sort -u`
Expected: Every linked `.md` file exists in `docs/`

- [ ] **Step 3: Verify no placeholders remain**

Run: `grep -i 'TBD\|TODO\|placeholder\|fill in\|implement later' docs/*.md`
Expected: No matches

- [ ] **Step 4: Run the project test suite to confirm no regressions**

Run: `pytest --tb=short -q`
Expected: 58 passed

- [ ] **Step 5: Commit any fixes**

```bash
git add docs/
git commit -m "docs: complete documentation suite"
```

---

## Summary

| Task | File | Content |
|------|------|---------|
| 1 | `docs/index.md` | Landing page with links |
| 2 | `docs/tutorial.md` (part 1) | Sections 1-7: setup, simulated data, ingest, trust, EWMA, transitions |
| 3 | `docs/tutorial.md` (part 2) | Sections 8-14: ratchet, metrics, briefing, MCP, the ratchet in action |
| 4 | `docs/the-ratchet.md` | Three feedback loops, measuring the ratchet, troubleshooting |
| 5 | `docs/configuration.md` | Complete config.toml reference |
| 6 | `docs/cli-reference.md` | Every command with synopsis and examples |
| 7 | `docs/integration.md` | Per-tool: kibitzer, lackpy, blq, jetsam, fledgling |
| 8 | `docs/architecture.md` | Plugin system, service layer, DuckDB schema, principles |
| 9 | `docs/mcp.md` | Resources, tools, read-only guarantee |
| 10 | Verification | Link check, placeholder scan, test suite |
