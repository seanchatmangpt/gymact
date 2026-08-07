# Changelog

## 26.8.7 - 2026-08-07

### Added

- Public-ontology GymAct application profile using PROF, PROV-O, P-PLAN, SOSA/SSN, WoT TD, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and Dublin Core Terms.
- Mechanical zero-custom-TBox admission check plus real pySHACL validation.
- Generic lifecycle operations represented as public `sosa:Procedure` resources.
- Pydantic v2 canonical runtime models separating semantic capability IRI from provider-local binding.
- Environment/EnvironmentProvider execution boundary and deterministic reference MemoryProvider.
- Receipted, idempotent environment materialization with optional external authority admission.
- Fail-closed external AuthorityResolver for consequential actuation, restore, and teardown.
- Monotonic authority requirements: environment/request configuration cannot downgrade provider policy.
- Per-episode concurrency serialization, exact in-process idempotent replay, and conflicting-key refusal.
- Bounded provider/authority timeouts plus payload and observed-state size limits.
- BLAKE3 write-ahead PREPARED and terminal FINAL receipts for consequential operations.
- In-memory and durable SQLite WAL/FULL-synchronization receipt ledgers with chain verification.
- Public PROV-O/SOSA receipt projection and EARL verification-result projection.
- Independent observation and verification; benchmark scoring remains a distinct layer.
- Native Python surfaces through FastAPI/OpenAPI, FastMCP, Typer, and FastStream.
- Portable JSON-schema contract export for ggen and independent compilers.
- ggen 26.8.6 → Rust procedure-table Gall checkpoint from the same packaged RDF profile.
- Python 3.11/3.12/3.13 CI, strict docs, clean wheel/sdist installation, and production container admission gates.

### Architectural rule

Python composes mature Python libraries directly. Rust/WIT/WASM projections are manufactured separately from the same admitted semantic graph. Provider bindings are implementation detail; public semantic capability identity is the interoperability boundary.
