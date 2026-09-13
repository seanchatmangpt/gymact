# ARD: The Chatman Ecosystem's 8-Layer Actuation Pipeline

Status: Accepted
Date: 2026-08-14
Scope: cross-repo (this document lives in `gymact` but most of its subject
matter is owned by sibling repositories, named explicitly below)

## Context

A user-authored essay ("Lets go through the Chatman ecosystem to automate
the $20/hr FDE") proposes mapping Forward-Deployed-Engineer work onto an
8-layer pipeline spanning several repositories:

```
Customer Mission
      │
      ▼
   fdegym            possibility graph: roles, lifecycle, capability space
      │
      ▼
 AutoFDE-Lab          EXPLORE: PDDL/RDDL planning, search, RL, falsification
      │
      ▼
    POWL              admitted partial-order work graph (control-flow authority)
      │
   ┌──┴──┐
   ▼     ▼
 ggen   GymAct         CONSTRUCT (manufacture)   /   DO (authority→actuate→verify→receipt)
   │     │
   └──┬──┘
      ▼
  receipts → OCEL → wasm4pm → process-intelligence → improved ontology/policy
```

This ARD records, for the whole ecosystem, which layer is real today and
which repository owns it — cross-checked against real source in this
session, not restated from the essay's own claims uncritically.

## Decision

**Layer ownership table** (standing tags: `ALIVE` = real, tested,
evidenced execution; `PARTIAL_ALIVE` = real but narrow/unproven at scale;
`ASPIRATIONAL` = named in docs/essay, no confirmed executing code found this
session; `OUT_OF_SCOPE(gymact)` = explicitly not gymact's job per
`.claude/rules/explore-exploit.md`):

| Layer | Owning repo | Standing (this session's evidence) |
|---|---|---|
| FDE role/capability ontology | `fdegym` | `PARTIAL_ALIVE` — 14 roles + lifecycle graph confirmed to exist; AWS operation graph grounded via botocore; Azure/GCP operation-level catalogs confirmed `ASPIRATIONAL` (named directly in the essay itself, not contradicted by anything found here) |
| Candidate exploration (PDDL/RDDL/search) | `autofde-lab` | `PARTIAL_ALIVE` — real `PDDLDomain` + registered `Astar` solver, real and tested (`tests/planning/test_fortune5_k8s_state_space_plan_chicago.py`), but only proven on a self-referential "plan autofde-lab's own roadmap" domain, not a real gymact-actuatable subject |
| Plan → POWL v2 projection | `autofde-lab` | `ALIVE` — `autofde_lab.fabric.powl.project_plan_to_powl` is real, already produced a committed `plan.powl.ttl` artifact, with a strict round-trip decoder |
| POWL execution (structural replay of an admitted graph) | `gymact` | `ALIVE` — `gymact.powl.executor` (structural-only, no actuation) + `gymact.powl_bridge` (two-phase replay → real `kernel.act()` calls), tested this session |
| Manufacture (ggen) | `gymact`'s `ggen/*-gym-pack` dirs, and elsewhere | `PARTIAL_ALIVE` — real ontology-driven Turtle→Pydantic composition patterns exist (`multicloud-gym-pack`, `mna-gym-pack`), but per `.claude/rules/ggen-boundary.md` gymact's own use of "ggen" is narrower than the essay's "manufacture everything" framing — see Consequences |
| DO (authority → actuate → verify → receipt) | `gymact` | `ALIVE` — `GymAct._authority_decision`/`AuthorityResolver`/`CapabilityScope`, independent `verify()`, `Receipt`+OCEL+EARL evidence, composition-admission gate; this is gymact's entire, narrow product |
| Deterministic MCP dispatch (gdmcp) | `gymact` (bridge only) + unmerged branch (compiler) | `PARTIAL_ALIVE` — `gymact.gdmcp_bpmn_bridge`/`gymact.mcp_process_control` (real, `ADAPT`-admitted dispatch/replay) are `ALIVE`; the ontology-driven *compiler* that generates new deterministic programs from a capability graph is still on an unmerged branch, not `main` |
| OCEL evidence / process mining | `wasm4pm`, `process-intelligence` | `ASPIRATIONAL` per this session's own prior finding — no real OCEL-discovery/O*-admission execution code was confirmed in `process-intelligence` (its README self-describes as a "research foundry" doctrine repo); `wasm4pm` was named as the more likely real location but was explicitly not investigated |
| Autonomic improvement loop | `process-intelligence` | `ASPIRATIONAL` — same finding as above; no confirmed executing code |

**gymact occupies exactly two of these nine rows**: POWL execution
(bridge-only) and DO. This ARD's decision is that gymact stays there —
formalizing `docs/actuation-layer-scope.md`'s existing scope statement as
the ecosystem-wide architectural decision, not inventing a new one.

## Consequences

- gymact will not grow a PDDL solver, an OCEL-mining/discovery module, or an
  RDF world-model/O*-admission layer. Any future request to add one of
  these to gymact should cite this ARD and redirect to `autofde-lab` /
  `process-intelligence` / `wasm4pm` respectively.
- gymact's own `ggen/*-gym-pack` ontologies are self-description (what
  gymact itself can do, and each action's consequence class) — not the
  essay's broader "ggen manufactures Terraform/K8s/SDK/docs from the
  admitted graph" ambition. That broader ggen-as-universal-manufacturer role
  is `OUT_OF_SCOPE(gymact)`; see `.claude/rules/ggen-boundary.md`.
- The essay's Azure/GCP-operation-graph gap is real but belongs to
  `fdegym`, not to gymact. gymact's own `multicloud.py` gym is a simulated
  cloud model (no real cloud API calls, by explicit design — see its module
  docstring) with equal-depth coverage across all three providers (26
  capabilities: AWS/Azure/GCP × IAM/Storage/Compute/Network-Security); it
  should not be conflated with fdegym's real-operation-grounding gap, and
  closing gymact's own multicloud simulation coverage does not close
  fdegym's gap.
- Any "close the loop end to end" demo therefore necessarily spans multiple
  repositories; no single-repo PR can deliver it. `docs/prd-gymact-
  actuation-layer.md` scopes gymact's own contribution to that demo.

## Non-goal

This ARD records architecture, not a business claim. It does not assert
that closing any of the gaps above makes the $20/hr-FDE thesis true, false,
sufficient, or necessary for any employment outcome — that causal claim was
explicitly investigated and found unsupported by this session's own prior
work (see the caveat preserved in this session's TPS-roadmap plan history:
labor-market causes — sector contraction, comp-band mismatch, referral
channel, interview variance, bias — were never evidenced one way or the
other by anything built here). Building any of this remains legitimate
engineering work on its own technical merits, independent of that claim.

## See also

- `docs/actuation-layer-scope.md` — gymact's own scope statement, which
  this ARD formalizes at the ecosystem level
- `docs/prd-gymact-actuation-layer.md` — gymact's product requirements,
  scoped by this ARD's decision
- `.claude/rules/explore-exploit.md`, `.claude/rules/ggen-boundary.md`,
  `.claude/rules/ontology.md`
