# PRD: gymact as the Chatman Ecosystem's DO/Actuation-Layer Product

Status: Draft
Date: 2026-08-14
Scope: `gymact` only — see `docs/ard-chatman-ecosystem.md` for the
ecosystem-wide layer map this PRD is scoped against.

## Product statement

Given an admitted `ActuationIntent` (or a POWL- or BPMN-compiled program of
them) produced by an upstream planner, gymact deterministically decides
admit/refuse under fail-closed authority, actuates, independently verifies
the real resulting world state, and produces a receipted, replayable
evidence trail. Nothing else. gymact is not the planner, not the observer,
not the ontology authority for the wider Chatman Ecosystem loop — per
`docs/actuation-layer-scope.md` and the ARD above.

## Current real capability inventory

| Capability | File | Standing |
|---|---|---|
| Fail-closed authority + capability-scope gate | `src/gymact/kernel.py` (`_authority_decision`), `src/gymact/authority.py` | `ALIVE` |
| Actuate + independent postcondition verify (never trusts actuator's own report) | `src/gymact/kernel.py` (`act`/`verify`), `src/gymact/verification.py` | `ALIVE` |
| Receipt + OCEL projection (`verified`/`world_changed`) | `src/gymact/ocel.py` | `ALIVE` |
| EARL evidence graph | `src/gymact/evidence.py` (`evidence_graph`, lines 183-220) | `ALIVE` |
| Composition-admission gate (reuse-before-create) | `src/gymact/composition.py`, `composition_inventory.py` | `ALIVE` |
| BPMN-compiled-program replay → `kernel.act()` | `src/gymact/gdmcp_bpmn_bridge.py` | `ALIVE` |
| POWL-admitted-graph replay → `kernel.act()` | `src/gymact/powl_bridge.py` | `ALIVE` |
| Deterministic MCP-call dispatch/gating | `src/gymact/mcp_process_control.py` | `ALIVE` |
| Multicloud simulation gym: 26 capabilities across AWS/Azure/GCP × IAM/Storage/Compute/Network-Security | `src/gymact/gyms/multicloud.py`, `ggen/multicloud-gym-pack/ontology.ttl` | `ALIVE` (confirmed by direct count this session: 26 `Capability(...)` entries, 4 `service-domain` SKOS concepts) — simulated, not real-cloud-grounded, by explicit design |
| `ActuationIntent` external wire contract (JSON Schema) | `src/gymact/contract.py` (`build_contract`), exposed via `gymact contract` CLI | `ALIVE` |
| Real, OCEL-evidenced infra automation (k8s, terraform) | `src/gymact/gyms/kubernetes_reconciliation.py`, `terraform_docker_apply.py` | `ALIVE` per real `reports/ocel/<subject>/episode.ocel.json` logs |

## Gaps relevant to the FDE thesis (each tagged with real status)

| Gap | Status | Owner if not gymact |
|---|---|---|
| Real (non-simulated) cloud-provider operation grounding | `OUT_OF_SCOPE(gymact)` — gymact's multicloud gym is deliberately a simulation surface; real API-grounded operation catalogs are `fdegym`'s job (AWS grounded via botocore there; Azure/GCP confirmed `ASPIRATIONAL` per the ARD) | `fdegym` |
| Security-control gym (real subprocess-backed firewall/security-group mutation, e.g. real `iptables`/`aws ec2`) | `PLANNED`, not built — scoped in this session's prior TPS-roadmap plan ("Phase 2") as a direct copy of `kubernetes_reconciliation.py`'s pattern | gymact (future work) |
| Drift-detection + jidoka stop-and-escalate router | `PLANNED`, not built — prior TPS-roadmap "Phase 3"; composes already-`ALIVE` `verify()` + `bpmn_runtime` + `mcp_process_control` | gymact (future work) |
| Time-boxed/escalating authority delegation | `PLANNED`, not built — prior TPS-roadmap "Phase 4"; new `AuthorityResolver` implementation, no kernel changes needed | gymact (future work) |
| Standing/continuous-episode OCEL (non-terminal FSM state) | `PLANNED`, largest/least-composable — prior TPS-roadmap "Phase 5"; needs a design spike against `process.py`/`ocel.py` before any estimate | gymact (future work) |
| Ontology-driven `gdmcp` *compiler* (generate new deterministic programs from a capability graph, not just replay a compiled one) | `PARTIAL_ALIVE` — real on an unmerged branch (`agent/gdmcp-sregym-deterministic-solutions`), not on `main` | gymact (merge/port decision, not yet made) |
| PDDL planning over a real gymact-actuatable subject | `OUT_OF_SCOPE(gymact)` | `autofde-lab` |
| OCEL-as-continuous-history / process mining / discovery | `OUT_OF_SCOPE(gymact)` | `wasm4pm` / `process-intelligence` |
| RDF-as-world-model / O* admission from raw observation | `OUT_OF_SCOPE(gymact)` | `autofde-lab` / `process-intelligence` |
| POWL-as-plan-*construction* (vs. gymact's execution-only role) | `OUT_OF_SCOPE(gymact)` | `autofde-lab` |

## Explicit non-requirements

gymact will not add: a PDDL solver, a POWL/graph *construction* API (only
execution of an already-admitted graph), an OCEL mining/discovery pipeline,
or an RDF-based O* admission layer. These are structural non-goals per
`docs/ard-chatman-ecosystem.md`'s Decision section, not a backlog gap —
requests for them should be redirected to the owning repo, not implemented
here.

## Where automation structurally stops (carried from the prior TPS roadmap)

Three already-hardened invariants each independently refuse anything past
detect-and-escalate: (1) `DenyAuthorityResolver` fails closed on *absence*
of an exact `authority_ref` — "use good judgment" cannot be expressed as a
`Capability` binding; (2) the composition gate's `BLOCKED_DISCOVERY` default
refuses any unclassified residual capability; (3) `verify()`'s independent-
re-query invariant cannot extend past the point where the "effect" being
verified is a human decision rather than a world-state transition. This
PRD's backlog (security-control gym → drift-escalation router → time-boxed
delegation) ends at a terminal human-escalation state by construction, not
by policy choice layered on top.

## See also

- `docs/ard-chatman-ecosystem.md` — the ecosystem-wide layer map this PRD
  is scoped against
- `docs/actuation-layer-scope.md` — the original scope statement
- `.claude/rules/composition-admission.md`, `.claude/rules/actuation-authority.md`
