# Changelog

## 26.8.7 - 2026-08-07

### Added

- Public-ontology GymAct application profile using PROF, PROV-O, P-PLAN, SOSA/SSN, WoT TD, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and Dublin Core Terms.
- Mechanical zero-custom-TBox admission check plus pySHACL validation.
- Pydantic v2 runtime models and deterministic reference environment/provider contracts.
- Authority-refused consequential actuation, idempotent replay, checkpoint/restore, independent verification, and bounded receipts.
- Native Python surfaces through FastAPI/OpenAPI, FastMCP, Typer, and FastStream.
- Python 3.11/3.12/3.13 CI and clean wheel/sdist installation validation.

### Architectural rule

Python composes mature Python libraries directly. Rust/WIT/WASM projections are manufactured separately from the same admitted semantic graph; GymAct does not generate Python boilerplate merely because ggen can.
