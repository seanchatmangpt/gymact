# GymAct engineering law

GymAct is a Python reference runtime for a public-semantic execution profile over bounded benchmark worlds.

## Semantic authority

- Do not add GymAct-owned OWL/RDFS classes or RDF/OWL properties merely for convenience.
- Prefer PROF, PROV-O, P-PLAN, SOSA/SSN, WoT TD/TM, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and DCTERMS.
- `urn:gymact:*` is for profile resources, ABox identities, SKOS concepts, and SHACL shapes.
- Before adding handwritten semantic machinery, prove the requirement cannot be represented as a public-ontology fact, constraint, profile, mapping, or projection.

## Consequence law

Never collapse these claims:

```text
request accepted != world changed != objective verified != benchmark scored
```

- An `authority_ref` is not permission.
- Required authority is fail-closed unless the injected `AuthorityResolver` explicitly admits the exact operation.
- A transport must never grant authority by itself.
- Provider failures must not disappear as successful or unreceipted consequential operations.
- Idempotency-key reuse with a different intent is a refusal, not a replay.

## Python vs Rust/ggen

Python composes mature Python libraries directly: Pydantic, FastAPI, FastMCP, Typer, FastStream, RDFLib, pySHACL, Gymnasium/PettingZoo where applicable.

Do not generate Python boilerplate with ggen when the host ecosystem already derives the surface correctly from Python types. ggen is the bridge from the same admitted RDF graph into Rust/WIT/WASM/static manufacture and an independent equivalence checkpoint.

## Evidence and standing

Use `UNKNOWN`, `PARTIAL_ALIVE`, `ALIVE`, `BLOCKED`, `BUILD_BROKEN`, `UNSUPPORTED`, and typed `REFUSED` reasons. Importability is not scenario execution. A benchmark integration retains its own execution standing.

Do not claim v26.8.7 release standing until exact-head CI has executed the semantic/runtime tests, Python matrix, package/wheel installation, docs build, lock validation, and container build required by the release contract.

## Change discipline

- Keep the generic kernel smaller than benchmark-specific integrations.
- New benchmark families should normally become providers/profiles, not new transports.
- Keep FastAPI, FastMCP, FastStream, and CLI semantics downstream of the same runtime.
- Preserve the public semantic graph as the cross-language authority boundary.
