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

## Consequence kernel

```text
MaterializationIntent / ActuationIntent
                 |
                 v
          authority resolver
                 |
                 v
         PREPARED receipt
                 |
                 v
      provider/environment DO
                 |
                 v
      independent observation
                 |
                 v
          FINAL receipt
```

The PREPARED record is appended before the provider call. A crash after a provider side effect can therefore leave an unresolved preparation that reconciliation can discover instead of making the actuation invisible.

Receipts are canonical-JSON BLAKE3 identities chained through `previous_receipt_digest`. The in-memory ledger is for bounded local/test worlds. `SQLiteReceiptLedger` provides durable append-only evidence using WAL, `synchronous=FULL`, and an immediate transaction for each append.

Raw provider/authority error output is not copied into receipts. GymAct stores bounded reason codes, exception type, and a digest. Provider and authority calls are time-bounded. Payload and state byte ceilings bound untrusted environment data.

## Authority

`authority_ref` is only an identifier supplied with an intent. When the provider/environment declares authority required, GymAct sends the exact semantic operation to an injected `AuthorityResolver`. The default resolver denies. A positive decision may carry a separate evidence reference that is bound into the receipt.

Authority requirements are monotonic:

```text
provider requires authority OR scenario/request raises authority
                         ↓
                  authority required
```

No request field can lower a provider-level authority requirement.

## Semantic admission

A materialized environment is not admitted merely because the provider returned an object. GymAct validates:

1. the environment structurally satisfies the Environment protocol;
2. its authority flag is typed;
3. its semantic capabilities are canonical `Capability` values;
4. those capabilities project to public SOSA/DCTERMS RDF;
5. real pySHACL accepts that RDF against the packaged profile;
6. the environment identity is an absolute IRI;
7. an initial independent observation can be obtained within time/size bounds.

Failure produces a typed BLOCKED materialization result and a terminal receipt; cleanup is attempted and cleanup failure is separately encoded in the reason code.

## Verification and scoring

```text
provider acknowledgement
        !=
observed consequence
        !=
verification result
        !=
benchmark score
```

`verify()` emits a separate `VerificationResult` and a receipted execution verdict. EARL can project that result publicly. Scoring remains benchmark-native and does not promote transport success into benchmark success.

## Rust/WASM bridge

The exact packaged RDF/SHACL profile and JSON-schema contract can be exported for ggen. v26.8.7 includes a Gall checkpoint:

```text
Python package
  ↓ export-profile
public RDF
  ↓ ggen 26.8.6
Rust procedure table
  ↓ rustc --test
executed projection
```

The Python library remains the ecosystem-native reference implementation. Rust/WIT/WASM are independent projections suitable for observational-equivalence and dependency-closed deployment.
