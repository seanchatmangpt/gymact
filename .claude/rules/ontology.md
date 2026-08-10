# Ontology Rule: Public Vocabularies First, No Custom TBox

## The rule

GymAct does not define its own OWL classes/properties for domain semantics. It is a
`prof:Profile` — an application profile that constrains and composes existing public
ontologies. Local `gymact:` IRIs are for *instances*, SKOS concepts, SHACL shapes, and
profile resources only — never for a competing class hierarchy.

Before adding any `gymact:SomeClass` or `gymact:someProperty`, search for an existing
public term that already means it. Only create a local term when a real search across
the vocabularies below turns up nothing usable — and name what was checked and why it
failed, not just that it failed.

## The vocabulary stack

| Concern | Vocabulary | Use for |
|---|---|---|
| Profile identity | W3C PROF | GymAct itself; links SHACL/docs/schemas |
| Provenance | PROV-O | activities, entities, agents, causal history |
| Prospective plans | P-PLAN | scenarios, steps, plan-vs-executed correspondence |
| Observation/actuation | SOSA/SSN | observations, actuations, actuators, results |
| Executable world model | W3C WoT TD/TM | environment, affordances, forms, security |
| Authority | ODRL | permissions, prohibitions, duties, policies |
| Executable constraints | SHACL | preconditions, goals, invariants, postconditions |
| Verification results | EARL | assertions, test subject, outcome, assertor |
| Metrics | DQV | metric, quality dimension, measurement |
| Quantitative scores | QUDT | quantity values, units |
| Datasets | DCAT | benchmark case corpora, distributions |
| Taxonomies | SKOS | standing, roles, interaction families |
| Time | OWL-Time | intervals, instants, deadlines |
| Metadata | DCTERMS | title, identifier, version, conformsTo |
| Evidence packaging | Workflow Run RO-Crate | portable run provenance |
| Software identity | DOAP, SPDX, Schema.org | repos, releases, SBOM |
| Geography | GeoSPARQL | geographic/region semantics |
| Privacy/personal data | DPV | personal-data/privacy processing scenarios |
| Software/package identity | SPDX | deployed software/package/image identity |
| Human identity | FOAF | simple public human-identity references |

## Gap documentation

When a candidate public vocabulary is searched and rejected for a given file or module,
that rejection must be named in the consuming file's own header or docstring — what was
searched and why it didn't fit — not silently omitted. This already happens in practice in
`ggen/multicloud-gym-pack/ontology.ttl`'s header comments; it is now an explicit repo rule,
not an incidental convention.

## Concrete replacements (do not reintroduce these classes)

- `GymDefinition` → `wot-tm:ThingModel`
- `EnvironmentInstance` → `wot-td:Thing`
- `ControlSurface` → `td:InteractionAffordance` / `td:Form`
- `Capability` → `td:ActionAffordance` / `sosa:Procedure`
- `Resource` → `prov:Entity` + `sosa:FeatureOfInterest` (multi-typed, not a new class)
- `Observation` → `sosa:Observation`
- `Action` (consequential) → `sosa:Actuation` / `prov:Activity`
- `Effect` → split: expected = SHACL shape; observed = `sosa:Result` + PROV derivation
- `WorldState` / `StateTransition` → `prov:Entity` + PROV causal pattern (used/wasGeneratedBy/wasDerivedFrom)
- `Scenario` → `p-plan:Plan` with `dct:type` pointing at a SKOS concept
- `Episode` → `prov:Activity` (optionally also `mls:Run` for ML-specific profiles)
- `Contestant`/`Harness`/`Verifier` → `prov:Agent` + `prov:Role`, not separate classes
- `Verifier`/`Verification`/`VerificationResult` → EARL (`earl:Assertion`, `earl:outcome`)
- `Objective`/`Constraint`/`Invariant` → SHACL node shapes, classified by a SKOS concept
- `AuthorityEnvelope` → `odrl:Policy`
- `Score`/`Metric` → DQV (+ QUDT when dimensional)
- `Receipt` → `prov:Bundle`, optionally packaged as RO-Crate
- `InteractionProfile` → `prof:Profile`

## Why

A custom parallel ontology means every new integration (MCP, BPMN, A2A, Rust, WIT, OTel)
has to re-derive meaning from scratch, and nothing interoperates with tooling that already
speaks PROV/SHACL/EARL/WoT. Reusing public terms means ggen's projections are free
consequences of well-understood semantics, not bespoke template logic.

## See also

- `.claude/rules/ggen-boundary.md` — what gets manufactured from this graph
- `.claude/rules/actuation-authority.md` — how ODRL policies gate `sosa:Actuation`
