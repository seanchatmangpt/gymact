# Crown compiled reference

This file is owned by `ggen/post-agi-crown-pack`. Its source of truth is the admitted RDF graph, not this Markdown projection.

## Pipeline

| Order | Stage | Meaning |
|---|---|---|
| 010 | `observe` | Observe raw world evidence |
| 020 | `admit` | Admit bounded observation |
| 030 | `select` | Select reversible candidate |
| 040 | `construct` | Construct powerless artifact |
| 050 | `authorize` | Resolve explicit authority |
| 060 | `actuate` | Actuate only through BRCE |
| 070 | `observe_consequence` | Observe external consequence |
| 080 | `verify` | Verify objective independently |
| 090 | `receipt` | Bind execution receipt |
| 100 | `replay` | Replay exact evidence |
| 110 | `standing` | Admit Crown standing |
| 120 | `compare` | Compare bounded SOTA frontier |

## Non-compensatory evidence

- `admitted_observation_digest` — Admitted observation identity
- `authority_evidence_ref` — Authority evidence identity
- `consequence_digest` — Observed consequence identity
- `experiment_digest` — Exact experiment identity
- `receipt_digest` — Receipt identity
- `replay_receipt_digest` — Replay receipt identity
- `subject_digest` — Exact subject identity
- `verifier_digest` — Independent verifier identity

## Standing-qualified metric space

- `actuation_efficiency` — Actuation efficiency
- `cost_efficiency` — Cost efficiency
- `generalization` — Generalization
- `latency_efficiency` — Latency efficiency
- `portability` — Portability
- `quality` — Quality
- `recovery` — Recovery
- `verifiability` — Verifiability

## Semantic transports

- `a2a` — A2A
- `bpmn` — BPMN
- `cli` — CLI
- `cloud_api` — Cloud API
- `http` — HTTP
- `mcp` — MCP
- `powl` — POWL
- `wasm` — WASM

## Owned outputs

The graph declares **13** ggen-owned projection targets; the admission gate refuses fewer than 10.

- `docs/crown-compiled-reference.md` — Compiled Crown reference
- `rust/crown/Cargo.toml` — Rust crate manifest
- `rust/crown/src/admission.rs` — Non-compensatory Crown admission
- `rust/crown/src/authority.rs` — Authority boundary constants
- `rust/crown/src/frontier.rs` — Pareto frontier calculus
- `rust/crown/src/lib.rs` — Rust Crown library facade
- `rust/crown/src/metrics.rs` — SOTA metric catalog
- `rust/crown/src/receipt.rs` — Receipt binding model
- `rust/crown/src/replay.rs` — Replay gate
- `rust/crown/src/stages.rs` — Crown stage catalog
- `rust/crown/src/transport.rs` — Semantic transport catalog
- `rust/crown/tests/gall.rs` — Gall cross-check proof
- `wit/gymact-crown.wit` — WIT Crown interface

These projections carry no execution authority. BRCE remains the only DO path.
