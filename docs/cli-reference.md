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
