# Explore-Module Archive

One line per deleted exploration scaffold: the invariant it probed. Deleted 2026-10-13 — zero non-test importers, each covered only by its own thin negative-path test. Recovery: `git log --follow -- src/gymact/<name>`.

## explore_ack family (flat modules + `explore_ack_epoch/` package)

- `explore_ack_admission.py` — admission is monotone in causal completeness: a witness gap refuses admission.
- `explore_ack_authority.py` — authority gates are phase-typed: admission phases past the leased ceiling are refused.
- `explore_ack_comparator.py` — ALL and QUORUM aggregation strategies remain semantically distinct completion predicates.
- `explore_ack_engine.py` — qualification composes admission+census+strategy+storage into a standing (PARTIAL_ALIVE vs UNKNOWN) without DO.
- `explore_ack_epoch/` — qualification is epoch-scoped: stale generations and DO-phase authority are refused; census over consumer ack states decides completeness.
- `explore_ack_identity.py` — subject identity is exact: short SHAs and non-exact keys are refused (`o/r@<40-sha>:consumer`).
- `explore_ack_invalidation.py` — invalidation requires a positive producer epoch; zero/negative epochs are refused.
- `explore_ack_protocols.py` — multiple reversible protocol candidates are preserved pre-selection with distinct quorum sizes.
- `explore_ack_receipt.py` — receipts replay only on byte-exact evidence; any mutation fails replay.
- `explore_ack_simulator.py` — failure simulation is deterministic: identical plans replay identically.
- `explore_ack_storage.py` — reversible storage alternatives are preserved before selection; durable+transactional selects sqlite.
- `explore_ack_topology.py` — dependency graphs fail closed on cycles.
- `explore_ack_witness.py` — witness discharge requires the receipt digest; digest-less discharge is refused.

## explore_consumer_binding/

- Probe: a consumer binding qualifies only against the exact current producer receipt+schema; drift is typed, leases are half-open, and scope never launders authority (qualifies without DO).

## explore_supersession/

- Probe: a new failure supersedes a stale green on the same exact subject; discovery preserves all capable reversible candidates; selection is deterministic and reversible; epochs require timezone + forward sequence; qualifies without DO.

## explore_verification/

- Probe: qualification standing is an axis-vector aggregate (contradictory axes refuse; failure dominates success; Pareto removes only dominated strategies); repository failure cannot be laundered by a mixed exact head; collection error is BUILD_BROKEN, not failure.

## explore_invalidation/

- Probe: invalidation events require timezone + replacement; cascade is transitive with preserved reasons and cycle/orphan refusal; schema drift forces renewal; failure→recovery standing transitions replay tamper-refused receipts — all without DO.
