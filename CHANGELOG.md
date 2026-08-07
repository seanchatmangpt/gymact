# Changelog

## 26.8.7 - 2026-08-07

### Added

- Public-ontology GymAct application profile using PROF, PROV-O, P-PLAN, SOSA/SSN, WoT TD, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and Dublin Core Terms.
- Mechanical zero-custom-TBox admission check plus real pySHACL validation.
- `sosa:Procedure` capability projection with SHACL-enforced title and READ/DO consequence classification.
- Pydantic v2 canonical runtime models separating semantic capability IRI from provider-local binding.
- Environment/EnvironmentProvider execution boundary and deterministic reference MemoryProvider.
- Receipted, idempotent environment materialization with optional external authority admission.
- Fail-closed external AuthorityResolver for consequential actuation, restore, and teardown.
- Per-episode concurrency serialization, exact idempotent replay, and conflicting-key refusal.
- Bounded provider failure receipts with error digests rather than arbitrary provider text.
- Independent observation and verification; benchmark scoring remains a distinct layer.
- Native Python surfaces through FastAPI/OpenAPI, FastMCP, Typer, and FastStream.
- Profile export for ggen/Rust/WIT/WASM or other independent compilers.
- Python 3.11/3.12/3.13 CI, strict docs, clean wheel/sdist installation, and production container admission gates.

### Architectural rule

Python composes mature Python libraries directly. Rust/WIT/WASM projections are manufactured separately from the same admitted semantic graph. Provider bindings are implementation detail; public semantic capability identity is the interoperability boundary.
