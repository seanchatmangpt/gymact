# Composition Admission: Reuse-Before-Create Law

## The rule

No new `gymact.gyms.*` provider (or comparable new-physics module) may be authored
before its required capability contract is checked against GymAct's existing,
evidenced component inventory via `gymact.composition.assert_create_authorized`.

`CREATE_PROVIDER` is authorized only when every residual capability — one no known
component supplies — has been given an explicit, evidenced `"world_physics"`
classification in `gymact.composition_inventory.KNOWN_CAPABILITY_CLASSIFICATIONS`.
An unrecognized residual capability resolves to `BLOCKED_DISCOVERY`, which refuses
creation exactly as hard as `REUSE`/`COMPOSE`/`ADAPT` do — incomplete discovery is
never grounds to create.

```text
Requirements  →  existing capability inventory  →  residual  →  classify residual
                                                                        │
                        ┌───────────────┬───────────────┬──────────────┴─────────────┐
                        ▼               ▼               ▼                            ▼
                     REUSE           COMPOSE          ADAPT                  CREATE_PROVIDER
              (1 component        (>1 components   (residual is           (residual is explicitly
               covers it)          jointly cover)   orchestration-only,    evidenced new world
                                                      not new physics)      physics)

                                                                       BLOCKED_DISCOVERY
                                                              (any residual capability has
                                                               no classification entry at all)
```

## Why five states, not "residual empty vs non-empty"

An earlier draft of this gate collapsed `residual != ∅` directly into
`CREATE_PROVIDER`. That silently converts `UNKNOWN → ABSENT`: a capability simply
missing from the hand-authored inventory table would license creating a new
provider, exactly the "invent before checking" failure mode this gate exists to
prevent. The fix distinguishes:

- a capability no component supplies but that is genuine orchestration/wiring
  over existing physics (`ADAPT`),
- a capability no component supplies that is genuinely new environment physics
  (`CREATE_PROVIDER`, but only when explicitly classified as such), and
- a capability nobody has evaluated yet (`BLOCKED_DISCOVERY` — the honest default).

## Practical checks when proposing a new provider

1. Express the new provider's justification as a `CapabilityContract` — the set of
   capability-id strings it would supply that nothing else does.
2. Run `gymact.composition.assert_create_authorized(contract,
   known_component_inventory(), known_capability_classifications())`.
3. If it raises, the reason names which of REUSE/COMPOSE/ADAPT/BLOCKED_DISCOVERY
   applies. `BLOCKED_DISCOVERY` means: add a real, evidenced classification entry
   first (to `gymact.composition_inventory`), not a code change to the decision
   logic in `gymact.composition`.
4. Both tables (`KNOWN_COMPONENT_CAPABILITIES`, `KNOWN_CAPABILITY_CLASSIFICATIONS`)
   are hand-authored and must carry real `evidence_ref` file:line citations —
   same discipline as `registry.py`'s `_BUILTINS` and
   `test_registry_completeness_chicago.py`'s `_INTENTIONALLY_UNREGISTERED` reasons.
5. `tests/test_composition_inventory_completeness_chicago.py` ("Court A") is the
   mechanical check that the inventory table itself hasn't silently drifted from
   real source — distinct from `test_composition_admission_chicago.py` ("Court
   B", which checks admission decisions given a fixed inventory). It AST-scans
   the real source tree for every gym `*Provider`, `AuthorityResolver`,
   `CapabilityScope`, and `PostconditionVerifier` implementation, plus the
   tracked OCEL functions and every `ggen/*-pack` with real `gates/*.rq` files,
   and requires each discovered candidate to be either a real `component_ref` in
   `KNOWN_COMPONENT_CAPABILITIES` or named in the test's own
   `_INTENTIONALLY_UNCATALOGED` allowlist with a specific, honest reason — the
   same discipline `test_registry_completeness_chicago.py` already applies to
   `registry._BUILTINS`.

## Scope limit, stated honestly

This gate does not perform automatic/semantic capability discovery. It is a pure
set-diff over two hand-authored, evidenced tables — the same trust model this
repo already uses for its registry allowlist. A capability contract phrased
differently than the table's ids will not automatically match; a human still
authors the contract and the table entries.

## See also

- `tests/test_registry_completeness_chicago.py` — the precedent this rule
  generalizes: mechanically ask "what actually exists?" before trusting a
  hand-maintained list.
- `.claude/rules/explore-exploit.md` — this repo builds only what has survived
  falsification; this gate is the mechanical enforcement of "reuse before build."
- `src/gymact/composition.py`, `src/gymact/composition_inventory.py`,
  `tests/test_composition_admission_chicago.py` — the implementation.
