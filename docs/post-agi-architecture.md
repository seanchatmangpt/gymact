# GymAct Post-AGI Architecture

## Constitutional invariant

GymAct is the bounded consequential execution substrate for benchmark and gym worlds. It is not an agent framework, planner, or ambient executor.

The lawful path is:

`observe -> admit -> select -> construct -> authorize -> actuate -> observe consequence -> verify -> receipt -> replay -> standing -> compare`

The only DO path is BRCE. Zero unreceipted actuation is non-negotiable.

## Post-AGI design target

A stronger planner or model must not require a stronger trust assumption. Increased cognition expands SELECT/CONSTRUCT space, while authority and consequence remain bounded by explicit admission, policy, execution limits, receipts, and replay.

The architecture therefore separates four spaces:

1. **Possibility space** — reversible candidate plans, constructions, transports, and world models.
2. **Admitted space** — candidates satisfying ontology, capability, authority, cost, and evidence constraints.
3. **Receipted reachable space** — external states reachable only through admitted BRCE transitions with complete receipts.
4. **Standing frontier** — replayable, verifier-bound outcomes eligible for bounded comparative SOTA claims.

## Completion law

No component may collapse these distinctions:

- generated != admitted
- selected != authorized
- accepted request != changed world
- changed world != verified objective
- verified objective != benchmark score
- benchmark score != comparative standing
- CI green != subject ALIVE
- named receipt != integrity-bound receipt
- connector object != mounted checkout

## Crown

`gymact.crown` is the promotion boundary from a verified consequential transition to comparative standing. Crown evidence binds subject identity, admitted experiment identity, admitted observation, authority evidence, observed consequence, verifier identity, receipt lineage, and replay evidence. Every required dimension is non-compensatory: missing replay or verification remains a typed refusal rather than a lower numeric score.

## Combinatorial maximalism

GymAct preserves maximal reversible lawful choices before irreversible selection. A failed edge changes topology; it does not collapse the graph. Planners and models may explore broad possibility graphs, but only formally admitted intents cross into BRCE.

## Semantic transport

Backend adapters are implementations of public semantic actions, not semantic authorities. MCP, CLI, HTTP, BPMN, POWL, A2A, cloud APIs, containers, and subprocesses are interchangeable execution fibers only when semantic round-trip invariance is verified.

## SOTA

SOTA is a bounded standing relation over an explicit comparison set and metric space. GymAct refuses universal or implicit claims. Pareto frontier calculation occurs only after Crown evidence is admitted and projected into `StandingEvidence`.

## Falsifiers

The architecture is falsified by any completed consequential transition lacking a receipt; a SOTA claim admitted without replay/verifier binding; authority obtained merely from model/planner output; semantic transport that changes declared action meaning without detection; or a benchmark result promoted from checkpoint evidence to crown standing.
