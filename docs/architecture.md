# GymAct architecture

GymAct treats benchmark actuation as execution against a bounded world, not as an adapter-specific command API.

## Semantic authority

The package owns an application profile and ABox identities, not a custom ontology TBox. Public ontologies provide the semantics:

- PROF: application-profile identity;
- PROV-O: entities, activities, agents, causal history, bundles;
- P-PLAN: prospective plan/step structure;
- SOSA/SSN: observation, actuation, and `sosa:Procedure` capabilities;
- WoT TD/TM: virtual worlds and interaction affordances;
- ODRL: permissions, prohibitions, duties, constraints;
- SHACL: executable structural/pre/postcondition constraints;
- EARL: verification assertions/results;
- DQV + QUDT: metrics and quantitative values;
- DCAT + SKOS + OWL-Time + DCTERMS: datasets, taxonomies, temporal and descriptive metadata.

`urn:gymact:*` resources are instances, concepts, shapes, and profile identifiers only.

A provider capability is a canonical Pydantic realization of a public `sosa:Procedure`:

```text
Capability.iri          -> RDF subject
Capability.title        -> dct:title
Capability.consequence  -> dct:type READ/DO SKOS concept
Capability.binding      -> provider-private implementation detail
```

The binding is intentionally not semantic authority. Two providers may bind the same public capability identity differently.

## Python composition

```text
semantic profile
      |
      v
canonical Pydantic models
      |
 +----+------+---------+----------+
 |           |         |          |
FastAPI   FastMCP    Typer    FastStream
OpenAPI     MCP       CLI      brokers
```

These are external Python dependencies, not ggen-produced reimplementations.

## Runtime boundary

```text
MaterializationIntent
       |
       v
EnvironmentProvider -- authority when provider declares setup consequential
       |
       v
Environment -- capabilities() -- real SHACL admission
       |
       +-- observe
       +-- actuate(Capability, payload)
       +-- verify
       +-- checkpoint / restore
       +-- teardown
```

Materialization and actuation have separate idempotency domains. A materialization failure never becomes an `Episode`; an admitted materialization returns an initial independent observation and receipt. Successful teardown is retained as a tombstone receipt so transport retries cannot cause a second teardown.

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

A provider acknowledgement cannot manufacture verification. A semantic capability with READ consequence cannot be smuggled through the actuation method.

## Authority

`authority_ref` is only an identifier supplied with an intent. When the provider/environment declares authority required, GymAct sends the exact semantic operation to an injected `AuthorityResolver`. The default resolver denies. A positive decision may carry a separate evidence reference that is bound into the receipt.

## Rust/WASM bridge

The exact packaged RDF/SHACL profile can be exported for ggen. ggen may manufacture static Rust/WIT/WASM types, dispatch tables, predicates, authority gates, verifier bindings, and fixtures. The Python library remains the ecosystem-native reference implementation; the Rust implementation is an independent projection suitable for observational-equivalence tests.
