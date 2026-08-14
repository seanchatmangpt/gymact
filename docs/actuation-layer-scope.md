# gymact's Scope: the BRCE / Actuation / Receipt Layer, Nothing Upstream

## Why this doc exists

In a broader ecosystem discussion, GymAct's role was described against an
eight-layer closed loop: RDF (meaning) → OCEL (observed history) →
admission into O* → PDDL (transition possibility) → POWL v2 (process
topology) → ggen (manufacture) → BRCE (authority gate) → actuation →
independent verification → receipt → back into OCEL. The correction that
prompted this doc: **gymact is just the actuation layer — planning (PDDL),
process construction, and world-observation aggregation happen upstream, in
autofde-lab and process-intelligence, not here.**

This doc states gymact's scope precisely, so it is never mistaken for — or
grown into — a planner, an observation-history store, or a world-model
ontology authority. Per this repo's own `CLAUDE.md`, it stays "smaller than
benchmark-specific integrations," and per
`.claude/rules/explore-exploit.md`, it is downstream of lab-repo admission,
not the repo that authors that admission.

## The real division of labor

```
 upstream (autofde-lab / process-intelligence / praxis)         gymact                downstream
 ─────────────────────────────────────────────────      ─────────────────────    ──────────────────
  RDF world-model, O* admission from raw observation             │
  OCEL as continuous, standing world history                     │
  PDDL planning: state-transition possibility                    │
  POWL v2: constructing process topology from a plan              │
  ggen: manufacturing the executable artifact                    │
              │                                                  │
   candidate ActuationIntent ───────────────────────────▶
                                                    identity
                                                    AuthorityResolver (fail-closed)
                                                    CapabilityScope
                                                    idempotency-key admission
                                                    consequence-class gate (READ vs DO)
                                                                   │
                                                              ACTUATION
                                                                   │
                                                    independent postcondition VERIFY
                                                    (never trusts actuate()'s own report)
                                                                   │
                                                              RECEIPT
                                                                   │
              ◀────────────────────────────────────  Receipt (verified, world_changed,
                                                       evidence_ref, authority_evidence_ref)
   Receipt feeds back into upstream's own OCEL/RDF,
   not into any standing store gymact itself owns
```

gymact receives an already-admitted candidate `ActuationIntent` from
whatever produced it — a human, an LLM, a PDDL planner, a POWL-driven
process, a BPMN workflow (`gymact.bpmn_runtime`), a deterministic MCP
dispatch (`gymact.mcp_process_control`) — and does exactly one thing with
it: decide, under fail-closed authority, whether it may become real, then
verify and receipt the result. It does not care, and should never be made
to care, how the intent was constructed upstream.

## What gymact really, evidently owns

| Piece | Real file(s) | What it actually does |
|---|---|---|
| The dam itself | `src/gymact/authority.py`, `GymAct._authority_decision` (`kernel.py`) | Fail-closed `AuthorityResolver` — refuses on *absence* of an admitted, exact `authority_ref`, not just explicit denial. Two real, documented hardening passes (`.claude/rules/actuation-authority.md`, 2026-08-08 and 2026-08-11) closed concrete unauthorized-by-default gaps found across 9 providers. |
| Capability/consequence gating | `CapabilityScope`, `Consequence.READ`/`DO` on every `Capability` | READ never crosses the authority gate at all; DO always does. Decided once, at the kernel level, never re-implemented per-provider. |
| Actuation + independent verification | `GymAct.act()`, `GymAct.verify()`, `Environment.observe()` | `verify()` polls real, independently re-queried state — never trusts `actuate()`'s own exit code or self-reported success. This is the "MCPValidity ≠ DOAuthority" invariant made concrete. |
| Receipt | `Receipt` model, `gymact.ocel`'s `verified`/`world_changed` attribute projection, `evidence.py`'s live `earl:Assertion` projection | Binds subject, capability, authority, pre-state, actuation, consequence, post-state, verification — the artifact that flows back to whatever called gymact. |
| Deterministic dispatch/execution surfaces | `gymact.bpmn_runtime`, `gymact.mcp_process_control`, `gymact.gdmcp_bpmn_bridge` | These execute an *already-constructed* process/program against the dam — they are consumers of admitted upstream structure, not producers of it. `bpmn_runtime.py` runs a `.bpmn` file someone else authored; it does not decide what that file should contain. |
| Composition-admission gate | `gymact.composition`, `composition_inventory.py` | Refuses to let gymact invent new provider physics when an existing component already supplies it (`REUSE`/`COMPOSE`/`ADAPT`/`CREATE_PROVIDER`/`BLOCKED_DISCOVERY`) — keeps the actuation layer itself from silently growing into something broader than it needs to be. |

## What gymact correctly does *not* own

- **PDDL planning** — no solver, no domain/problem-file generation exists
  in gymact, and none should be added here. `ProjectionKind.PDDL`/`PPDDL`
  in `lab.py`/`contract.py` are symbolic tags naming a projection target
  another system (autofde-lab) produces — not a claim that gymact plans.
- **POWL as process *construction*** — `gymact.powl` is real, but it is
  used here only as an **execution** engine for an already-admitted
  partial-order graph. It does not construct that graph from a plan;
  that construction, wherever POWL v2 is used for it, happens upstream.
- **OCEL as continuous, standing world history** — `gymact.ocel` writes
  one schema-valid log per bounded episode
  (`reports/ocel/<subject>/episode.ocel.json`, materialize→act→verify→
  teardown, TEARDOWN a hard terminal state). It is real evidence *of
  gymact's own actuations*, not the continuous observed-world history the
  broader loop's OCEL layer describes — that standing history, if it
  exists, lives in process-intelligence.
- **RDF as world-model / O\* admission from raw observation** — every
  `ggen/*-gym-pack/ontology.ttl` in gymact is a capability/consequence
  *self-description* (what this provider can do, and each action's
  consequence class) — not the world-model ontology an upstream admission
  pipeline runs raw observations through to produce O*. Two different RDF
  uses; gymact only needs the narrower one.
- **ggen-as-general-manufacture** — gymact consumes `ggen/*-gym-pack`
  ontologies as data (via `OntologyDrivenProvider`) or, for the Rust/WASM
  side, defers entirely to the `ggen` binary per
  `.claude/rules/ggen-boundary.md`. It is not where manufacture policy is
  decided.

## Why this boundary matters

Keeping gymact narrow is not a limitation to apologize for — it is the
point. The essay's own thesis is that no single system should hold both
the power to *propose* a transition and the power to *authorize* it. gymact
being "just the actuation layer" is the correct, load-bearing instance of
that separation: whatever proposes intents (a planner, a human, an LLM, a
POWL-driven workflow) has zero ambient authority here, and gymact itself
has zero opinion about how those intents should have been constructed. That
asymmetry — broad, unconstrained proposal upstream; narrow, fail-closed
admission at the dam — is what `.claude/rules/actuation-authority.md`
already encodes, and this doc exists so a future contributor never "fixes"
gymact's narrowness by growing it into a planner or a world-model store.

## See also

- `.claude/rules/actuation-authority.md` — the fail-closed invariant this
  doc describes at the architecture level.
- `.claude/rules/explore-exploit.md` — gymact's position downstream of
  lab-repo (autofde-lab) admission, stated as this repo's own law.
- `.claude/rules/composition-admission.md` — the mechanism that keeps this
  layer from silently growing scope.
- `.claude/rules/ggen-boundary.md`, `.claude/rules/ontology.md` — the two
  narrower, gymact-scoped uses of ggen and RDF described above.
