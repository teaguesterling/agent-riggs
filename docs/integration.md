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
