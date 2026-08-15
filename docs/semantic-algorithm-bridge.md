# Canonical Semantic Bridge

## Purpose

Use one admitted public-semantic graph across domain gyms instead of duplicating vocabularies or hand-maintaining equivalent projections. RDF/XML, JSON-LD, and Turtle inputs normalize to one deterministic canonical identity with source provenance.

## Shared contract

The bridge exposes public executable terms already defined by P-PLAN, SOSA, and WoT TD. It adds mechanical checks for exact source and triple counts, required IRI subsets, required predicates, executable exact sets, source digests, canonical graph digests, and identifier uniqueness.

The normalization path is read-only: it derives canonical bytes in memory and does not write generated projections. Re-running the same admitted inputs must therefore produce the same digest without changing source files.

## Consumers and boundaries

Fortune-5 enterprise architecture and Sony/media scenarios are ABox consumers of this contract, not reasons to add a competing GymAct class hierarchy. rrgym and LifeGym should consume the same contract as executable-domain clients rather than create bespoke semantic cores.

GymAct continues to own world law and observed consequences. AutoFDE Lab continues to own planning, falsification, and admission. ggen continues to manufacture derived Rust/WIT/WASM artifacts from admitted graphs rather than decide domain policy.
