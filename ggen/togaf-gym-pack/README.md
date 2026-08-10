# TOGAF Gym Pack

This pack implements the enterprise-architecture gym as a **public-ontology profile followed by a deterministic `ggen` projection**.

```text
public Open Group source identifiers
        -> SKOS / PROV-O / ORG / P-PLAN / OSLC RM / DCAT / ODRL
        -> SPARQL admission + SHACL/EARL task courts
        -> admitted ABox
        -> ggen sync run
        -> Rust task catalog + WIT contract + compiled reference + receipt
```

## Fence

This repository does not define `togaf:Phase`, `togaf:Requirement`, `togaf:Artifact`, or any other TOGAF-specific OWL/RDFS type system. Local `urn:gymact:togaf:*` IRIs are limited to profile resources, ABox individuals, SKOS concepts, and SHACL/EARL courts. The gates reject local predicates and local TBox declarations.

The pack also does **not** redistribute the TOGAF Standard, definitions, diagrams, templates, or body text. It records public source identifiers and short public phase labels from Open Group web pages, then adds independently authored synthetic enterprise data and gym contracts. Users remain responsible for applicable Open Group licensing when they use TOGAF documentation or commercial TOGAF training/tooling.

## Public semantic stack

- W3C PROF: profile identity
- W3C PROV-O: plans, entities, activities, derivation, provenance
- P-PLAN: executable/training plans
- W3C ORG: enterprise, architecture office, architecture board, roles
- W3C SKOS: ADM phase/domain/task/artifact classifications
- OASIS OSLC RM 2.1: requirements and traceability
- W3C DCAT + DCTERMS: architecture resources and metadata
- W3C ODRL: governance permission boundary
- W3C SHACL + EARL: task oracles/falsifiers

## Gym surface

The admitted graph contains the ten public ADM labels (Preliminary, Requirements Management, and Phases A-H) and ten synthetic tasks. Each task points to a SHACL/EARL oracle. The scenario is invented for GymAct; it is not copied from TOGAF training material.

`ggen` projects three ephemeral surfaces into a consumer:

- `src/lib.rs` -- phase/task/oracle catalog;
- `wit/gymact-togaf-gym.wit` -- language-neutral gym contract;
- `docs/compiled-reference.md` -- provenance-bearing semantic reference.

Generated outputs are not canonical and `consumer/togaf-gym/**` is intentionally not checked in. The graph, courts, gates, queries, templates, and `ggen.toml` are canonical; `ggen` recreates outputs and emits its receipt.

## Verification

```bash
GGEN_BIN=/path/to/ggen pytest -q tests/test_ggen_togaf_gym_pack.py
cd ggen/togaf-gym-pack
ggen graph validate --files ontology.ttl --shapes courts/shapes.ttl
ggen sync run
```

The Python test executes graph parsing, all three SPARQL gates, ontology-purity checks, and exact phase/task coverage. With `GGEN_BIN` (or on the Python 3.13 GitHub Actions leg using the pinned v26.8.8 release), it also executes `ggen graph validate --shapes`, proves a missing OSLC trace is refused, runs `ggen sync run` twice, requires byte-identical projections, and requires the generation receipt.
