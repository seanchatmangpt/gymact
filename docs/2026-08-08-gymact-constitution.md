# GymAct Constitution (Working-Backwards Draft)

Proposal/derivation document, not yet reflected in README.md. Follows the existing
`docs/2026-08-08-*.md` pattern (see `docs/2026-08-08-multicloud-gym.md`,
`docs/2026-08-08-level4-novel-task-discovery.md`). Grounded directly in two real surveys
of this repo's current code and ontology (kernel.py, providers.py, models.py,
`.claude/rules/ontology.md`, `profile.ttl`, `profile.shacl.ttl`), not in aspiration.

## The working-backwards promise

GymAct is a universal substrate for bounded consequential environments. It knows what a
gym is. It does not know what AutoFDE is, what CUBE is, what a Kubernetes cluster is, or
what Terraform is — those are providers behind a Protocol boundary, never special cases
inside the kernel.

This is not a design aspiration under negotiation. Survey 0's real grep over `kernel.py`
(`grep -niE "cube_counter|terraform|kubernetes|docker|browsergym|harbor|inspect_ai"`)
returned zero matches, and direct reading of the `GymAct` class body confirms every
operation dispatches only through the `Environment`/`EnvironmentProvider` Protocol
methods plus a generic `provider.name` string lookup. The promise is already kept at the
kernel layer; this document names the contract precisely enough that it stays kept as new
providers (multicloud, browsergym, inspect_ai, ...) are added.

## The gym algebra

```
G = (S, O, C, A, Gamma, T, V, R)
```

| Symbol | Meaning | Grounding |
|---|---|---|
| `S` | WorldState space | `prov:Entity`, produced/consumed by the PROV causal pattern |
| `O` | Observation space | `sosa:Observation` |
| `C` | Capability set | `sosa:Procedure` / `td:ActionAffordance` (already instantiated: `urn:gymact:shape:capability` targets `sosa:Procedure` today) |
| `A` | Action space | `sosa:Actuation` / `prov:Activity` |
| `Gamma` | Authority admission | `odrl:Policy` |
| `T` | Transition relation | `prov:Entity` linked by `prov:used` / `prov:wasGeneratedBy` / `prov:wasDerivedFrom` |
| `V` | Verification function | `earl:Assertion` / `earl:outcome`, independent of the actuator's own report |
| `R` | Receipt/replay record | `prov:Bundle`, optionally RO-Crate-packaged |

Every symbol in `G` maps onto an existing public class from the vocabulary stack in
`.claude/rules/ontology.md`. Survey 2's direct reading of that file plus `profile.ttl`
and `profile.shacl.ttl` confirms this mapping requires zero new RDF classes or
properties — including the two symbols (`T` composition/ordering, `R` replay) that are
not literally named in `ontology.md`'s "Concrete replacements" table but decompose
cleanly into the same PROV/EARL/P-PLAN primitives already in use. Where plain typing
under-constrains a multi-hop structural relationship (Transition ref completeness,
Episode-as-container, Composition well-formedness), the fix is a new `sh:NodeShape` under
`urn:gymact:shape:*`, targeting a public class, following the exact pattern already
established by `urn:gymact:shape:capability` — never a new class. See
`src/gymact/ontology/gym_algebra.shacl.ttl` for the concrete shapes this constitution
requires (Transition, Episode, Composition), kept additive and separate from
`profile.shacl.ttl` so the existing capability contract is untouched.

## The five-operation split

```
OBSERVE | SELECT | CONSTRUCT | DO | VERIFY
```

GymAct owns exactly three of these five: **OBSERVE**, **DO**, **VERIFY**. It does not own
**SELECT** (choosing which capability/action to invoke — that is a contestant/harness
decision, made by whatever agent sits above the kernel) or **CONSTRUCT** (synthesizing a
novel plan, payload, or provider integration — lab/AutoFDE-layer work per
`.claude/rules/explore-exploit.md`'s admission pipeline).

This split is visible directly in `providers.py`'s `Environment` Protocol (survey 0):
`observe()`, `actuate()` (DO), and `verify()` are kernel-owned Protocol methods with no
provider-name branching anywhere in `kernel.py`. `capabilities()` exposes what SELECT can
choose from without performing the selection; `checkpoint()`/`restore()`/`teardown()` are
lifecycle support for OBSERVE/DO/VERIFY, not a fourth or fifth owned operation.
`materialize()` and `discover()` are kernel-level operations distinct from the 8-method
per-environment surface, matching the `Operation` enum in `models.py` (which separates
DISCOVER/MATERIALIZE from the 8 environment operations, per survey 0).

GymAct refusing to own SELECT/CONSTRUCT is not a missing feature — it is the boundary
that keeps the kernel smaller than benchmark-specific integrations, per
`CLAUDE.md`'s change-discipline section.

## Core concepts and relations

Every concept below is grounded in a real, already-adopted public vocabulary term. None
requires a new `gymact:` class or property, per `.claude/rules/ontology.md`.

| Concept | Public grounding | Notes |
|---|---|---|
| Gym | `prof:Profile` (this profile) constraining a bounded `wot-tm:ThingModel` | the algebra `G` itself, described |
| World | `wot-td:Thing` | a materialized environment instance |
| WorldState | `prov:Entity` | a point in `S`; PROV causal pattern (`used`/`wasGeneratedBy`/`wasDerivedFrom`) links states across a Transition |
| Observation | `sosa:Observation` | result of OBSERVE |
| Observer | `prov:Agent` + `prov:Role` (`urn:gymact:role:harness` or `:contestant`) | never a separate class — `profile.ttl` already instantiates these two roles |
| Capability | `sosa:Procedure` / `td:ActionAffordance` | classified READ/DO via `urn:gymact:scheme:consequence`, exactly as `models.py`'s `Consequence` StrEnum and `urn:gymact:shape:capability` already do |
| Action | `sosa:Actuation` / `prov:Activity` | result of DO on a DO-classified Capability |
| AuthorityEnvelope | `odrl:Policy` | crossed before any `Consequence.DO` actuation, per `.claude/rules/actuation-authority.md` |
| Goal | `p-plan:Plan` target / SHACL node shape (expected postcondition) | plan-adjacent, per `.claude/rules/ontology.md`'s `Objective`/`Constraint` row |
| Invariant | SHACL node shape, classified via SKOS | same row as Goal — an invariant is a Goal that must hold at every WorldState, not just terminally |
| Transition | `prov:Entity` + PROV causal pattern | constrained by `urn:gymact:shape:transition`: before/after WorldState refs, an Action ref, an AuthorityEnvelope ref, an Observation ref |
| Consequence | split: expected = SHACL shape, observed = `sosa:Result` + PROV derivation | mirrors `models.py`'s `Receipt.intended_effects` vs. `world_changed`/`verified` split |
| Episode | `prov:Activity` (optionally also `mls:Run`) | constrained by `urn:gymact:shape:episode`: must `prov:generated` at least one Transition |
| Receipt | `prov:Bundle`, optionally RO-Crate-packaged | matches `models.py`'s `Receipt` model field-for-field (subject/capability/authority refs, pre/post-state digests, `world_changed`, `verified`) |
| Replay | PROV causal chain re-`prov:used`-ing the same Entity sequence + `earl:Assertion`/`earl:outcome` for the conformance verdict | no new class; decomposes into existing PROV+EARL terms per survey 2 |
| Projection | `prov:wasDerivedFrom` chain from an admitted semantic graph into a Rust/WIT/WASM artifact | the ggen boundary, per `.claude/rules/ggen-boundary.md` |
| SubGym | `prof:Profile` narrower than the parent Gym, or a `p-plan:Step` `pplan:isStepOfPlan` a Composition | a constituent gym referenced by a Composition |
| Composition | `p-plan:Plan` / `p-plan:Step` with `pplan:isStepOfPlan` | constrained by `urn:gymact:shape:composition`: must reference at least one SubGym |

## The G0-G4 standing ladder

A new, GymAct-native standing ladder, distinct from and layered below the AutoFDE
Level 4 crown. It answers a narrower question than AutoFDE's crown does: not "can this
system discover and complete novel tasks," but "does this specific gym integration
actually satisfy the algebra `G` end to end, with evidence." It is the standing GymAct
itself is responsible for proving before any AutoFDE-layer claim about a gym is
meaningful.

| Level | Name | Criterion |
|---|---|---|
| G0 | Described | A `prof:Profile`/`wot-tm:ThingModel` exists for the gym; `capabilities()` returns a well-formed, SHACL-conformant `Capability` tuple. No claim about execution. |
| G1 | Observable | A real `Environment.observe()` call against a real materialized `World` returns a real `sosa:Observation` — `request accepted`, per `CLAUDE.md`'s consequence law, not yet `world changed`. |
| G2 | Consequential | A real `Environment.actuate()` call on a DO-classified Capability, admitted through a real `odrl:Policy` (`AuthorityEnvelope`), produces a real Transition with pre/post `prov:Entity` state digests — `world changed`, not yet independently verified. |
| G3 | Verified | An independent `Environment.verify()` call (or external EARL assertor) establishes `earl:outcome` truth about the post-state — matching `.claude/rules/ocel-standing.md`'s requirement that a gym's "working" claim rest on a real, schema-valid, conformant-replay, `solved=True` OCEL log, never a pytest verdict or an actuator's own success report. |
| G4 | Composable | The gym participates as a SubGym inside a real Composition (`p-plan:Plan` satisfying `urn:gymact:shape:composition`) with at least one other SubGym, and that Composition itself reaches G3 as a unit. |

### How G0-G4 composes with AutoFDE Level 4

G0-G4 is not a competing crown — it is the substrate crown sits on. AutoFDE's Level 4
("novel task discovery," per `docs/2026-08-08-level4-novel-task-discovery.md`) requires
SELECT and CONSTRUCT: choosing which capability to exercise and synthesizing new task
instances the kernel was never told about in advance. Per this document's five-operation
split, GymAct explicitly does not own SELECT/CONSTRUCT — so a system claiming AutoFDE
Level 4 crown standing over a *specific gym* is only meaningful if that gym has first
reached **G3 (Verified)** on OBSERVE/DO/VERIFY, and reached **G4 (Composable)** if the
crown claim spans multiple gyms composed together (survey 0's confirmed zero-branching
kernel is exactly what makes composing arbitrary gyms into one Composition safe: no gym's
provider identity leaks into the kernel's dispatch logic, so composing N gyms costs
nothing extra at the kernel layer). Concretely:

```
AutoFDE Level 4 crown (SELECT + CONSTRUCT, novel task discovery)
                         │  requires, per gym in scope
                         ▼
        GymAct G3 (Verified) — or G4 (Composable) when the
        crown claim spans a Composition of multiple SubGyms
                         │
                         ▼
        GymAct G0..G2 (Described → Observable → Consequential)
```

A crown claim resting on a gym that has not itself reached G3 is exactly the collapse
`CLAUDE.md`'s consequence law forbids — `request accepted != world changed != objective
verified != benchmark scored` — relocated one layer up, from a single episode to an
entire capability crown.

## See also

- `.claude/rules/ontology.md` — the vocabulary-first discipline this document's every
  concept mapping is bound by
- `.claude/rules/actuation-authority.md` — the AuthorityEnvelope/Gamma admission gate
- `.claude/rules/ocel-standing.md` — the evidentiary standard G3 (Verified) is built on
- `.claude/rules/explore-exploit.md` — where CONSTRUCT-level admission work belongs
  (lab, not this repo)
- `src/gymact/ontology/gym_algebra.shacl.ttl` — the concrete SHACL contract for
  Transition/Episode/Composition this document requires
- `tests/test_gym_algebra_shapes.py` — real pyshacl validation of that contract
