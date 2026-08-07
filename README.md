# GymAct v26.8.7

GymAct is a Python reference implementation of a **public-semantic execution profile for bounded benchmark and gym worlds**.

The semantic authority is not a custom GymAct ontology. It is a W3C `prof:Profile` composed from public vocabularies including PROV-O, P-PLAN, SOSA/SSN, WoT Thing Description, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and Dublin Core Terms.

Python-native surfaces compose mature libraries directly:

- Pydantic v2 for canonical typed runtime models;
- FastAPI for HTTP/OpenAPI;
- FastMCP for agent-facing MCP tools;
- Typer for the operator CLI;
- FastStream for broker-neutral event-driven commands;
- RDFLib + pySHACL for semantic loading and real conformance checks.

The Rust/WASM path is deliberately separate: `gymact export-profile` materializes the same admitted RDF/SHACL graph for ggen to manufacture Rust/WIT/WASM/static projections. Python composes; Rust manufactures.

## Core laws

```text
request accepted != world changed != objective verified != benchmark scored

semantic capability identity != provider-local binding

authority_ref != authority decision
```

A capability is represented publicly as `sosa:Procedure`. GymAct's canonical Python `Capability` carries the procedure IRI, title, READ/DO consequence class, and a provider-private binding. Real SHACL validates the public semantic projection before an environment is admitted.

Consequential environments are fail-closed. GymAct invokes an injected `AuthorityResolver` and proceeds only after an explicit positive decision. With no resolver configured, required authority is refused even when the caller provides an `authority_ref` string.

Materialization, actuation, restore, and teardown all produce typed dispositions and receipts. Provider error text is hashed into `error_digest`; receipts retain bounded failure type rather than copying arbitrary provider output.

Idempotency is semantic rather than best-effort:

- same materialization key + same intent → same result;
- same materialization key + different intent → `REFUSED:IDEMPOTENCY_KEY_CONFLICT`;
- same actuation key + same intent → same result;
- same actuation key + different intent → refusal;
- concurrent identical actuation is serialized per episode and cannot double-actuate;
- successful teardown is replayable as the same receipt.

## Quick start

```bash
pip install gymact

gymact version
gymact validate-profile
gymact demo
gymact demo --authority
gymact export-profile ./gymact-profile
```

Run the HTTP surface:

```bash
gymact serve --host 127.0.0.1 --port 8000
```

Python:

```python
from gymact import (
    ActuationIntent,
    AllowListAuthorityResolver,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
)

AUTHORITY = "urn:example:authority"
SET = "urn:gymact:memory:capability:set"

runtime = GymAct(
    authority_resolver=AllowListAuthorityResolver({AUTHORITY})
)
runtime.register_provider(MemoryProvider())

materialized = await runtime.materialize(
    MaterializationIntent(
        provider="memory",
        config={"initial": {"healthy": False}, "requires_authority": True},
    )
)
assert materialized.episode is not None

episode = materialized.episode
result = await runtime.act(
    ActuationIntent(
        episode_id=episode.episode_id,
        capability=SET,
        payload={"key": "healthy", "value": True},
        authority_ref=AUTHORITY,
    )
)
verification = await runtime.verify(episode.episode_id, {"healthy": True})
```

`AllowListAuthorityResolver` is a deterministic reference implementation for tests and isolated local gyms. It is explicitly not a substitute for BRCE or another production policy decision point.

## Surfaces

FastAPI:

```python
from gymact.surfaces.fastapi import create_app
app = create_app(runtime)
```

FastMCP:

```python
from gymact.surfaces.fastmcp import create_mcp
mcp = create_mcp(runtime)
```

FastStream accepts an externally selected broker, so GymAct does not choose Kafka, NATS, RabbitMQ, Redis, or MQTT on behalf of the caller:

```python
from gymact.surfaces.faststream import create_stream_app
app = create_stream_app(broker, runtime)
```

All surfaces use the same Pydantic intents/results and the same runtime. They do not independently reimplement GymAct semantics.

## Semantic authority

`src/gymact/ontology/profile.ttl` contains the application profile and controlled ABox identities. It deliberately defines **zero GymAct OWL/RDFS classes or RDF/OWL properties**. `urn:gymact:*` is reserved for profile resources, ABox identities, SKOS concepts, and SHACL shapes.

`ProfileAuthority.validate()` runs real pySHACL plus a mechanical zero-custom-TBox gate. `ProfileAuthority.validate_data()` admits extension ABoxes. `ProfileAuthority.validate_capabilities()` projects canonical Pydantic capabilities into SOSA/DCTERMS RDF and validates them through the same SHACL shapes.

## Runtime boundary

```text
EnvironmentProvider
      │
      ├── materialization authority? ──► AuthorityResolver
      │
      ▼
Environment
      ├── capabilities() ──► sosa:Procedure profile validation
      ├── observe()
      ├── actuate(Capability, payload) ──► authority when consequential
      ├── verify()
      ├── checkpoint()/restore()
      └── teardown()
```

The bundled `MemoryProvider` is a deterministic executable reference gym. It exists to validate the generic contract, not to stand in for external benchmark execution.

## Release admission

v26.8.7 is release-ready only when exact-head CI proves:

- public profile + extension ABoxes parse and SHACL-conform;
- no custom GymAct TBox leaks into profile, shapes, or extension data;
- provider capabilities are validated as public `sosa:Procedure` resources;
- materialization and actuation authority are fail-closed;
- idempotency and concurrent replay do not duplicate consequences;
- provider failures are bounded and receipted;
- FastAPI executes a real reference episode;
- FastMCP executes in-process through its real Client;
- FastStream executes the broker-neutral lifecycle;
- Typer validates/exports the installed semantic profile;
- Python 3.11/3.12/3.13 pass tests, coverage, lint, and format gates;
- wheel/sdist metadata and clean-wheel profile resources pass;
- strict docs build passes;
- the production container builds, boots, and answers `/health`;
- the resolved `uv.lock` is committed and subsequently checked rather than silently regenerated.

External benchmark integrations retain their own execution standing. Importability is never promoted into scenario-execution standing.
