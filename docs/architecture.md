# GymAct architecture

GymAct treats benchmark actuation as execution against a bounded world, not as an adapter-specific command API.

## Semantic authority

The package owns an application profile and ABox identities, not a custom ontology TBox. Public ontologies provide the semantics:

- PROF: application-profile identity;
- PROV-O: entities, activities, agents, causal history, bundles;
- P-PLAN: prospective plan/step structure;
- SOSA/SSN: observation and actuation;
- WoT TD/TM: virtual worlds and interaction affordances;
- ODRL: permissions, prohibitions, duties, constraints;
- SHACL: executable structural/pre/postcondition constraints;
- EARL: verification assertions/results;
- DQV + QUDT: metrics and quantitative values;
- DCAT + SKOS + OWL-Time + DCTERMS: datasets, taxonomies, temporal and descriptive metadata.

`urn:gymact:*` resources are instances, concepts, shapes, and profile identifiers only.

## Python composition

```text
semantic profile
      |
      v
Pydantic runtime models
      |
 +----+------+---------+----------+
 |           |         |          |
FastAPI   FastMCP    Typer    FastStream
OpenAPI     MCP       CLI      brokers
```

These are external Python dependencies, not ggen-produced reimplementations.

## Runtime boundary

```text
EnvironmentProvider
        |
        v
    Environment
  observe / actuate
 verify / checkpoint
 restore / teardown
        |
        v
      Episode
```

The reference `MemoryProvider` is executable evidence for the contract. Real benchmark packages should implement the same semantic boundary or provide a profile adapter.

## Consequence law

```text
accepted request
      !=
observed effect
      !=
verified objective
      !=
benchmark score
```

A transport acknowledgement cannot manufacture verification. Consequential operations that require authority are refused when no authority reference is supplied.

## Rust/WASM bridge

The same admitted RDF graph can be consumed by ggen to manufacture static Rust/WIT/WASM types, dispatch tables, predicates, authority gates, verifier bindings, and fixtures. The Python library remains an ecosystem-native reference implementation; the Rust implementation is an independent manufactured projection suitable for observational-equivalence testing.
