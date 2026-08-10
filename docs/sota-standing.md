# SOTA standing

GymAct treats **SOTA as a standing relation, not a scalar score**.

A comparative result is admitted only when it binds an exact subject, experiment, receipt, verifier, and successful replay. Only then may it enter a declared metric space and Pareto comparison.

```text
observed -> admitted -> executed -> changed -> verified -> receipted -> replayed -> compared
```

`gymact.sota` implements the deliberately small 80/20 calculus:

- `StandingEvidence`: minimum comparison bindings;
- `FrontierResult`: standing-qualified metric vector;
- `dominates`: Pareto dominance with identical metric-space enforcement;
- `pareto_frontier`: deterministic nondominated set;
- `sota_claim`: a **bounded** claim relative to an explicit comparison set.

The module refuses missing receipt/verifier/subject/experiment bindings, unreplayed evidence, invalid metrics, and metric-space mismatch. It never promotes a local comparison into a universal SOTA claim.

This preserves the distinction:

```text
benchmark score != standing
checkpoint != crown
local frontier != universal SOTA
```

The falsifier is straightforward: remove replay or a receipt binding and the candidate must be refused before optimization. Add a comparator that Pareto-dominates the candidate and the bounded SOTA claim must become false.
