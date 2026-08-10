# post-agi-crown-pack

This pack manufactures the independent Rust/WIT side of GymAct's Crown/SOTA architecture.
It follows `.claude/rules/ggen-boundary.md`: Python is not code-generated. The admitted
public-semantic graph is the source; Rust/WIT/proof/reference artifacts are projections.

## Law

`observe -> admit -> select -> construct -> authorize -> BRCE DO -> observe consequence -> verify -> receipt -> replay -> standing -> compare`

- SELECT and CONSTRUCT carry no ambient execution authority.
- BRCE remains the only DO path.
- zero-unreceipted-actuation is invariant.
- Crown evidence is non-compensatory.
- SOTA is bounded to an explicit comparison set and identical metric space.
- no output path may contain `generated`.
- the ontology must declare at least 10 owned projection targets; this pack declares 13.

## Replay

From this directory:

```bash
ggen sync run
cargo test --manifest-path ../../rust/crown/Cargo.toml
ggen sync run
git diff --exit-code -- ../../rust/crown ../../wit/gymact-crown.wit ../../docs/crown-compiled-reference.md
```

A successful render is only a checkpoint. Crown standing additionally requires a real
consumer, independent verification, exact source/toolchain identity, and a ggen receipt.
