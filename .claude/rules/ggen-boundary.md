# ggen Boundary: Rust/WASM Manufacture, Not Python Codegen

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

Do NOT use ggen for anything covered by `python-native.md`.

## Why the split exists

Python's dependency ecosystem (Pydantic → FastAPI/FastMCP/Typer/FastStream) already
derives HTTP/MCP/CLI/broker surfaces correctly from typed models — regenerating that in
ggen would create a second, divergent implementation of the same thing for no benefit.
The Rust side has no equivalent ecosystem shortcut; ggen is what closes that gap and is
also what lets a generated capability run outside a Python process (WASM sandboxing,
native performance, deployment portability).

## See also

- `.claude/rules/ontology.md` — the graph ggen reads from
- `.claude/rules/python-native.md` — the Python side ggen does not duplicate
