# ggen Boundary: Rust/WASM Manufacture and Declared Synthetic OCEL

## The rule

`ggen` exists to manufacture the Rust/WASM side of GymAct from the admitted semantic graph
— the ecosystem Python doesn't already give us cheaply. It is a bridge, not a Python
template engine.

```
GymAct admitted semantic graph (public ontologies + ABox)
                │
      ┌─────────┴─────────┐
      ▼                   ▼
 Python-native        Rust-native (ggen)
 (see python-native.md)    │
                     ┌─────┼──────┐
                     ▼     ▼      ▼
                   Rust   WIT   WASM
                   types  ABI   components
```

Use ggen when the target is:
- a Rust type/predicate/dispatch table
- a WIT interface / WASM component
- a static, compiled closure meant to run with no RDF engine in the hot path
  ("semantic-model-ignorant runtime" — Smithy's term for the same idea)
- an independent implementation used to cross-check the Python implementation
  (Gall checkpoint: same admitted input → same disposition in both)
- an explicitly declared **synthetic OCEL 2.0 history/result** manufactured from
  admitted world/planner/generator specifications for evaluation, falsification,
  rare-event coverage, or training.

Do NOT use ggen for ordinary Python API/code generation covered by `python-native.md`.

## Synthetic OCEL is manufacture, never execution

A GGen-manufactured OCEL trace MAY be observationally indistinguishable from a real or
executed trace under the admitted operational projection. That is a desired fidelity
property.

Its privileged audit projection MUST always preserve:
- `origin=GGEN_MANUFACTURED`
- `observed_execution=false`
- `manufactured_trace=true`
- claimed actor
- generator identity
- generator-spec digest
- world-model digest
- deterministic seed
- trace digest

A manufactured trace MUST NOT:
- call BRCE or an actuator as part of manufacture;
- carry or mint an execution receipt;
- claim that the modeled planner/actor actually executed;
- confer execution `ALIVE` standing;
- erase or forge its audit provenance.

Thus `ggen` can manufacture the **possible history** while GymAct/BRCE remains the only
path that can manufacture authority-bound evidence of an actual DO.

## Why the split exists

Python's dependency ecosystem (Pydantic → FastAPI/FastMCP/Typer/FastStream) already
derives HTTP/MCP/CLI/broker surfaces correctly from typed models — regenerating that in
ggen would create a second, divergent implementation of the same thing for no benefit.
The Rust side has no equivalent ecosystem shortcut; ggen is what closes that gap and is
also what lets a generated capability run outside a Python process (WASM sandboxing,
native performance, deployment portability).

Synthetic OCEL is a separate permitted manufacture because it is a data/evidence-surface
projection, not a second Python runtime implementation.

## See also

- `.claude/rules/ontology.md` — the graph ggen reads from
- `.claude/rules/python-native.md` — the Python side ggen does not duplicate
- `.claude/rules/ocel-standing.md` — synthetic traces cannot substitute for executed standing
- `docs/synthetic-ocel-results.md` — canonical result and dual-projection contract
