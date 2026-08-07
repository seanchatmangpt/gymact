# GymAct v26.8.7

GymAct is a Python reference implementation of a **public-semantic execution profile for bounded benchmark and gym worlds**.

It does not invent a competing benchmark ontology. The packaged semantic authority is a W3C `prof:Profile` composed from public vocabularies including PROV-O, P-PLAN, SOSA/SSN, WoT Thing Description, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and Dublin Core Terms.

Python-native surfaces compose mature libraries directly:

- Pydantic v2 for typed runtime models;
- FastAPI for HTTP/OpenAPI;
- FastMCP for agent-facing MCP tools;
- Typer for the operator CLI;
- FastStream as the event-broker application boundary;
- RDFLib + pySHACL for semantic loading and conformance.

The Rust/WASM path is intentionally separate: ggen can consume the same admitted semantic graph to manufacture static Rust/WIT/WASM projections without forcing Python to reimplement its own ecosystem.

## Invariants

GymAct keeps these claims separate:

```text
request accepted != world changed != objective verified != benchmark scored
```

A consequential action is refused when its environment requires authority and the request carries no authority reference. GymAct itself never grants authority.

## Quick start

```bash
pip install gymact

gymact version
gymact validate-profile
gymact demo
```

Run the HTTP surface:

```bash
gymact serve --host 127.0.0.1 --port 8000
```

Python:

```python
from gymact import ActuationIntent, GymAct, MemoryProvider

runtime = GymAct()
runtime.register_provider(MemoryProvider(requires_authority=True))
```

FastAPI:

```python
from gymact import GymAct, MemoryProvider
from gymact.surfaces.fastapi import create_app

runtime = GymAct()
runtime.register_provider(MemoryProvider())
app = create_app(runtime)
```

FastMCP:

```python
from gymact.surfaces.fastmcp import create_mcp
mcp = create_mcp(runtime)
```

FastStream accepts an existing broker so GymAct does not choose Kafka, NATS, RabbitMQ, Redis, or MQTT on behalf of the caller:

```python
from gymact.surfaces.faststream import create_stream_app
app = create_stream_app(broker, runtime)
```

## Semantic authority

`src/gymact/ontology/profile.ttl` contains GymAct's application profile and controlled ABox identities. It deliberately defines **zero GymAct OWL classes, object properties, or datatype properties**.

`ProfileAuthority.validate()` runs pySHACL and also enforces the zero-custom-TBox invariant mechanically.

## Runtime model

The reference runtime is intentionally small:

```text
EnvironmentProvider -> Environment -> observations / actuations / verification
                            ^
                            |
                         Episode
```

Providers are ordinary Python dependencies. A benchmark integration should map into this boundary rather than create another transport implementation.

The bundled `MemoryProvider` is a deterministic executable reference gym used to validate authority refusal, idempotency, state transitions, verification, checkpoint/restore, receipts, HTTP, MCP, and CLI behavior.

## Standing

v26.8.7 is considered release-ready only when the repository's CI proves:

- semantic profile parses and SHACL-conforms;
- no custom GymAct TBox terms exist;
- authority refusal is executable;
- idempotent replay does not duplicate actuation;
- observed consequence is independently verified;
- FastAPI, FastMCP, Typer, and FastStream bindings import and construct;
- Python 3.11, 3.12, and 3.13 tests pass;
- wheel/sdist build and metadata validation pass.

Gym-specific execution standing remains the responsibility of each integration and must not be inferred from importability.
