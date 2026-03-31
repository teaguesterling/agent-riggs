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
