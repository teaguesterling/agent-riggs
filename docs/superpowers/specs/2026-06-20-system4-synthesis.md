# Agent Riggs — System 3*/System 4 Synthesis

Reconciles two lineages of agent-riggs design:

- **The audit spec** (`2026-03-29-agent-riggs-design.md`, and the built system):
  a deterministic, plugin-based **System 3\*** — cross-session audit. Trust by
  arithmetic, candidates by SQL, promotions human-gated. Design Principle #3:
  *"No LLM in the analysis loop."*
- **The generative brainstorm** (2026-06): agent-riggs as a meta-loop that
  *generates* prompts + datasets and uses lackpy/LLM agents to **interpret log
  results** and refine the suite — fed by a "duck-parser" substrate where all
  telemetry is queryable tables.

The goal here is not to pick a winner. Each has a real blind spot. The
Viable-System-Model lens the audit spec already adopts is what reconciles them.

---

## The reframe: they are different VSM subsystems, not competitors

The audit spec calls itself **System 3\*** (Beer's audit channel — reliable,
retrospective monitoring of *what happened*). The brainstorm is reaching for
**System 4** (intelligence — forward-looking, exploratory, *what could be /
what should we try*). Those are **adjacent functions with different epistemics**,
and conflating them is what made "no LLM" feel like it contradicted "generate
interpretations."

- **System 3\* (audit)** must be trustworthy and reproducible. Determinism is
  *correct* here. Principle #3 belongs to System 3\*.
- **System 4 (intelligence)** is where hypotheses, classifications of the messy
  long tail, and experiment designs come from. Exploration — and LLMs — belong
  *here*, because its outputs are **proposals to be tested**, not decisions.

So the synthesis adds a System-4 layer the spec never had, *without* loosening
System 3\*.

---

## What each design got wrong (be honest about both)

**The audit spec's blind spot: it cannot tell correlation from causation.**
Its ratchet promotes on *frequency* ("grep used 89× with a structured
alternative → graduate the interceptor"). But this session proved (the kibitzer
A/B) that **frequency ≠ a nudge will change behavior**. Promoting on observation
alone can graduate interceptors that do nothing — or that agents were going to
heed anyway. The spec's ratchet is **passive**: it waits for evidence to arrive
and never *produces* the counterfactual. That's a genuine gap, not a detail.

**The brainstorm's blind spot: it threatens auditability.** "Improvements
generated, not coded" and "LLM interprets the logs" — taken literally — put a
non-reproducible model in the loop that *acts*. A ratchet's whole value is that
it only tightens with a human's say and every decision traces to evidence. An
LLM in the *decision* loop quietly destroys that. The brainstorm also risks a
premature meta-level (a *generator of interpreters*) before we have 2–3
interpreters to generalize from.

---

## The reconciling principle (refines Principle #3, does not repeal it)

> **System 4 may write *data* (classifications, experiment results) and *propose*
> (hypotheses, experiments, candidates). Only System 3\* (specified measurement)
> and System 5 (the human ratchet) may *decide*. Every promotion or transition
> still traces to a SQL query, a measured experiment, or a human.**

The membrane is **propose-vs-decide**, not LLM-vs-no-LLM. An LLM that writes a
label into a column, or drafts an A/B to run, is *not* "in the analysis loop" —
the analysis (trust, candidates, decisions) still runs on specified code over
that data.

---

## The synthesized architecture

```
        ┌──────────────────────── System 4 (NEW: intelligence) ────────────────────────┐
        │  • Active experiments  — generate + run A/Bs to PRODUCE causal evidence       │
        │  • Long-tail classify  — lackpy/LLM labels failures patterns miss (writes data)│
        │  • Hypotheses          — "what might explain this / what's worth testing?"     │
        └───────────────┬───────────────────────────────────────────────┬──────────────┘
                        │ writes data / proposes                          │ proposes experiments
                        ▼                                                 ▼
        ┌──────────────────────── System 3* (KEEP: deterministic audit) ───────────────┐
        │  trust (EWMA) · failure_stream · session_summaries · SQL candidate views ·    │
        │  measured experiment results · the ratchet (promote/reject/defer, audited)    │
        └───────────────┬──────────────────────────────────────────────────────────────┘
                        │ candidates + evidence
                        ▼
                System 5 (human) — turns the ratchet → writes sibling-tool configs
```

### What's preserved from the audit spec (unchanged)
- The plugin architecture, the DuckDB store, the trust engine (arithmetic EWMA),
  failure stream, session summaries, `ratchet_decisions` audit trail.
- "Reads everything, writes nothing to other tools." Human-gated promotions.
- SQL candidate views as the *decision substrate*.

### What's added (System 4)
1. **An experiment loop (a 4th ratchet loop).** The existing three loops are
   observe→promote. Add **Loop 0 — evidence generation**: hypothesis → designed
   A/B → measured lift → feeds the existing loops. *The kibitzer A/B + nudge_lift
   we hand-built this session is the first instance; agent-riggs generalizes it
   into an experiment factory.* A frequency candidate should not graduate until
   an experiment shows the graduation actually moves behavior.
2. **LLM-assisted long-tail classification.** The spec's `classify` step is
   pattern-matching; an LLM/lackpy labels the failures patterns miss — writing
   `event_category`/`failure_category` values, never decisions.
3. **The duck-parser substrate.** Generalize ingestion so *all* telemetry —
   including Claude transcripts (a `duck_hunt`-style parser; `FledglingSource` is
   the first cut) — lands as uniform queryable tables. Then "generate a dataset"
   = "generate SQL," which lackpy can do, and the hand-rolled `bypass_probe` /
   `nudge_lift` collapse into SQL views.

### The safeguard that makes System 4 honest: recursive trust
The spec scores trust in *agent behavior*. Extend it to score trust in
**System-4's own outputs**: did an LLM classification correlate with outcomes?
did a hypothesis survive its experiment? Low-trust generators get down-weighted
or flagged for human review. This is the QC for the fuzzy periphery and a
natural extension of the trust engine that already exists — and it's the part
that's genuinely novel: *a system that meta-learns which of its own interpreters
to believe.*

---

## Agent Riggs as a recursive viable system

A correction to the framing above. agent-riggs is the suite's **System 3\***, but
by Beer's recursion theorem a viable system *contains* viable systems — so
agent-riggs is **itself a full VSM (Systems 1–5)**, not an audit function alone.
"Add System 4" is not bolting an appendage onto a 3\*-only thing; it is
*completing agent-riggs's own stack*. Mapping the internal tiers doubles as a
gap analysis:

| Internal tier | agent-riggs component | state |
|---|---|---|
| **S1 Operations** | ingest sources + per-tool pipelines (read → classify → score → store) | ✅ built |
| **S2 Coordination** | service/assembly layer + shared DuckDB store (plugins don't collide) | ✅ built |
| **S3 Control** | the ratchet *mechanism* + config thresholds (regulate ops, find candidates) | ✅ built, deterministic |
| **S3\* Audit (internal)** | **recursive trust** — auditing its own sources / classifications / interpreters | ❌ missing → this synthesis adds it |
| **S4 Intelligence** | hypotheses, experiment design (the A/B factory), LLM interpretation | ❌ missing → this synthesis adds it |
| **S5 Policy/Identity** | charter + invariants; *what S4 may do autonomously vs must escalate* | ⚠️ implicit (in docs as principles, not a governing tier) |

So the built system is **S1–S3-heavy, S4/3\*/S5-light** — and the synthesis is
exactly the upper tiers it lacks. That, not novelty for its own sake, is the
argument for building it now.

**This *homes* the open questions instead of leaving them loose:**
- **Experiment governance** is agent-riggs's own **S5/S3**: its internal policy on
  what its S4 may perturb and with what blast radius — escalating to the *suite's*
  S5 (the human / CLAUDE.md) for anything risky. The human-gated promotion means
  agent-riggs deliberately **delegates its *ultimate* S5 upward** to the human;
  but it still needs an *explicit internal S5* to govern its own S4.
- **Recursive trust** is its internal **S3\***: the audit channel turned on
  itself, scoring whether its own intelligence is reliable. Not an add-on to the
  trust engine — the same function applied recursively.

**Suite-level recursion (orientation):** kibitzer = the suite's within-session
control (S1–S3); agent-riggs = the suite's S3\* (audit) — carrying the
intelligence the suite needs *via its own internal S4* looking outward at suite
behavior; the human + CLAUDE.md = the suite's S5. Each tier, one level down, is a
whole viable system again.

## Sequencing (each step standalone-valuable; earn the meta-level)

0. **Duck-parser for transcripts** — transcripts → table; rewrite `bypass_probe`
   as SQL to validate. Wins for fledgling *and* lays the substrate. Lowest risk.
1. **Wire the session's work into the existing store** — `bypass_probe` /
   `nudge_lift` / kibitzer trials become an ingest source + SQL views. The
   designed home already exists; this is mostly plumbing.
2. **Loop 0 — the experiment layer** — generalize the kibitzer A/B: agent-riggs
   designs/registers an experiment, kibitzer runs it, results land in the store,
   the ratchet gates on *measured* lift. Closes the correlation/causation gap.
3. **Long-tail classification (lackpy)** — only after 1–2 are real; LLM labels
   the failures patterns miss, with recursive-trust scoring from day one.
4. **The generator** — generate (SQL dataset + prompt) per interpretation task —
   only once 2–3 hand-written interpreters exist and a generator *falls out*.
   Do **not** build the meta-level speculatively.

---

## Open questions
- **Experiment governance.** Who/what may an agent-riggs experiment perturb, and
  with what blast radius? (The kibitzer A/B only withheld a nudge — low risk.
  An experiment that changes a *mode* is higher.) Needs a System-5 gate too.
- **lackpy vs Claude for System 4.** lackpy's own charter excludes judgment.
  Likely: lackpy for mechanical SQL/dataset shaping; Claude (or the human) for
  the judgment proposals. Confirm the split.
- **Statistical floor.** Experiments need pre-registered minimum N before the
  ratchet reads them (the A/B power problem). Where does that live — config?
- **Does Principle #3's wording change in `architecture.md`?** If we adopt the
  refined version, the canonical doc should say "no LLM in the *decision* loop."
