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
