# Protocol → Gym compiler

GymAct can manufacture gym *definitions* from self-describing protocol surfaces without
manufacturing one Python provider per subject.

```text
MCP tools/list ─┐
A2A AgentCard ──┼─> discover O -> admit O* -> ProtocolGymSpec -> RDF ABox -> ggen
LSP initialize ─┘                                      │
                                                       └-> generic ProtocolGym runtime
```

## Law

Protocol advertisement is structural evidence only.

`advertised != authorized != executed != consequence observed != verified != ALIVE`

Every discovered MCP tool and A2A skill is conservatively a DO candidate requiring
external authority. LSP query capabilities are READ; edit/command candidates remain DO.
A protocol-specific admission policy may narrow this later, but discovery alone may not.

Python composes native protocol clients. ggen manufactures the independent Rust/WIT,
schema, reference, and Gall-checkpoint projections from the admitted public-semantic
graph. No output is placed under a `generated/` directory.

## ggen gym

`GgenProvider` is distinct from the existing `GgenLegacyVerifierProvider`. The latter
wraps the ggen-legacy v26.8.1 verifier. The current ggen gym admits a real consumer
project containing `ggen.toml` plus an explicit `bundle_root`. It resolves the consumer's
declared ontology, template, and path-pack dependencies; every resolved path and symlink
must remain inside that admitted bundle root. It preflights file/byte bounds, copies an
isomorphic dependency-closed bundle into a private temporary world, and exposes:

- `graph validate` — READ
- `doctor run` — READ
- `sync run` — DO, BRCE/authority-gated by GymAct
- `receipt verify` — READ

The source checkout is never the actuation target. Observation hashes the complete copied
bundle tree and records whether the consumer's `.ggen/receipts/latest.json` exists.

## Standing

A discovered protocol gym begins `STRUCTURAL`. Promotion to `ALIVE` requires the ordinary
GymAct consequence path: real session, admitted authority where needed, BRCE execution,
independent observation, verification, receipt, and replay.
