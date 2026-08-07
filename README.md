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

A consequential operation is **fail-closed** when its environment requires authority. An `authority_ref` is only a reference; it does not grant permission. GymAct invokes an injected `AuthorityResolver` and proceeds only after an explicit positive decision. With no resolver configured, required authority is refused.

Idempotency is also semantic rather than best-effort: replaying the same intent/key returns the same result; reusing a key for a different intent is refused; concurrent identical requests are serialized per episode so they cannot double-actuate.

Provider/tool failures are returned as typed, receipted `BLOCKED` results rather than disappearing behind unreceipted exceptions.

## Quick start

```bash
pip install gymact

gymact version
gymact validate-profile
gymact demo
gymact demo --authority
```

Run the HTTP surface:

```bash
gymact serve --host 127.0.0.1 --port 8000
```

Export the semantic authority for ggen/Rust or another external compiler:

```bash
gymact export-profile ./gymact-profile
```

Python:

```python
from gymact import AllowListAuthorityResolver, GymAct, MemoryProvider

runtime = GymAct(
    authority_resolver=AllowListAuthorityResolver({"urn:example:authority"})
)
runtime.register_provider(MemoryProvider(requires_authority=True))
```

`AllowListAuthorityResolver` is a bounded deterministic reference implementation for isolated gyms/tests. It is not a substitute for BRCE or another production policy decision point.

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

The broker-neutral dispatcher implements the same core lifecycle operations (`discover`, `create_episode`, `observe`, `act`, `verify`, `checkpoint`, `restore`, `teardown`) before a broker family is selected.

## Semantic authority

`src/gymact/ontology/profile.ttl` contains GymAct's application profile and controlled ABox identities. It deliberately defines **zero GymAct OWL/RDFS classes or RDF/OWL properties**.

`ProfileAuthority.validate()` runs pySHACL and also enforces the zero-custom-TBox invariant mechanically. `ProfileAuthority.export()` materializes the exact packaged RDF and SHACL resources for an external compiler such as ggen.

## Runtime model

The reference runtime is intentionally small:

```text
EnvironmentProvider -> Environment -> observations / actuations / verification
                            ^
                            |
                         Episode

consequential operation -> AuthorityResolver -> explicit decision -> Environment
```

Providers are ordinary Python dependencies. A benchmark integration should map into this boundary rather than create another transport implementation.

The bundled `MemoryProvider` is a deterministic executable reference gym used to validate authority refusal, admitted authority, idempotency, concurrent replay, state transitions, verification, checkpoint/restore, provider-failure receipts, HTTP, MCP, streaming dispatch, and CLI behavior.

## Standing

v26.8.7 is considered release-ready only when repository CI proves:

- semantic profile parses and SHACL-conforms;
- no custom GymAct TBox terms exist;
- authority reference without an admitted resolver decision cannot actuate;
- concurrent/idempotent replay does not duplicate actuation;
- provider failures remain receipted and do not claim success;
- observed consequence is independently verified;
- FastAPI executes a real reference episode;
- FastMCP executes in-process tools through its real Client;
- FastStream's broker-neutral dispatcher executes the core lifecycle;
- Typer profile export works from the installed wheel;
- Python 3.11, 3.12, and 3.13 tests pass;
- strict docs build passes;
- wheel/sdist build and metadata validation pass;
- the resolved `uv.lock` is persisted and subsequently checked rather than regenerated silently.

Gym-specific execution standing remains the responsibility of each integration and must not be inferred from importability.
