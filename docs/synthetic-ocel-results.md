# Synthetic OCEL 2.0 Gym Results

GymAct treats OCEL 2.0 as the canonical result surface for both executed and
manufactured gym histories.

## Result calculus

```text
WORLD   -> canonical OCEL object state
INTENT  -> proposed transition
DELTA   -> OCEL event/object mutations
RECEIPT -> authority + actual execution evidence
```

Domain observations, rewards, termination flags, benchmark scores, planner
transcripts, and other legacy gym outputs are projections over the OCEL
history. They are not the canonical evidence object.

## Three origins

Every `OCELGymResult` has privileged provenance:

- `REAL_OBSERVED`: imported from an actually observed external system.
- `GYM_EXECUTED`: derived from GymAct's actual receipt trail.
- `GGEN_MANUFACTURED`: synthetic history manufactured from admitted
  generator/world specifications.

The operational projection is OCEL-only. This allows a fidelity court to ask
whether a consumer can distinguish a manufactured history from a real or
executed history without leaking a synthetic-only label into the domain data.

The audit projection always includes provenance. A manufactured result is
therefore allowed to be **operationally indistinguishable** but is never
**provenance-indistinguishable**.

## Evidence fence

A GGen-manufactured trace has:

```text
observed_execution = false
manufactured_trace = true
origin = GGEN_MANUFACTURED
execution_receipt_refs = []
```

and records content-addressed identities for the trace, generator
specification, world model, plus the seed and claimed actor.

Manufacture cannot mint execution receipts, call BRCE, or confer execution
standing. For example, a trace manufactured to look like Planner X solved an
episode proves only that the admitted Planner-X specification admits that
history. It does **not** prove Planner X actually ran.

## Fidelity court

Given a real/executed result `R` and manufactured result `M`:

```text
operationally_equivalent(R, M)
```

tests exact equivalence of the canonical operational OCEL projections. More
general discriminators may apply an admitted observation projection `q` and
measure:

```text
q(R.ocel) ~= q(M.ocel)
```

For a balanced real/synthetic corpus, discriminator accuracy approaching
chance is evidence of fidelity for that observer class. Audit provenance must
remain perfectly recoverable regardless of operational fidelity.

## GGen handoff

`export_manufacturing_bundle()` now emits
`synthetic-ocel-result-contract.jcs.json`. GGen packs can consume that
machine-readable contract alongside GymAct's runtime contract. Their output is
admitted through `manufacture_synthetic_ocel_result()`, which validates the
official OCEL 2.0 schema and binds deterministic trace/spec/model digests.

This makes synthetic histories useful for:
- evaluator-first development;
- rare-event and failure coverage;
- adversarial falsifier manufacture;
- process-intelligence training corpora;
- planner-specification conformance;
- privacy-preserving world populations;
- domain bootstrapping before live integrations exist.
