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

The Rust/WASM path is deliberately separate: `gymact export-profile` and `gymact export-contract` materialize the same admitted semantics for ggen to manufacture Rust/WIT/WASM/static projections. Python composes; Rust manufactures.

## Core laws

```text
request accepted != world changed != objective verified != benchmark scored

semantic capability identity != provider-local binding

authority_ref != authority decision
```

A capability is represented publicly as `sosa:Procedure`. GymAct's canonical Python `Capability` carries the procedure IRI, title, READ/DO consequence class, and a provider-private binding. Real SHACL validates the public semantic projection before an environment is admitted.

Consequential environments are fail-closed. GymAct invokes an injected `AuthorityResolver` and proceeds only after an explicit positive decision. With no resolver configured, required authority is refused even when the caller provides an `authority_ref` string. Authority requirements are monotonic: request/config data may raise the required authority but cannot lower a provider-level requirement.

## Consequence evidence

Materialization, actuation, restore, and teardown are protected by write-ahead evidence:

```text
intent
  ↓
authority decision
  ↓
PREPARED BLAKE3 receipt
  ↓
provider consequence
  ↓
independent observation
  ↓
FINAL BLAKE3 receipt
```

This means a process failure after a consequential provider call cannot erase the fact that an admitted actuation was prepared. Receipts form an append-only BLAKE3 chain. GymAct includes both an in-memory ledger for bounded local/test environments and a durable SQLite WAL/FULL-synchronization ledger for persistent evidence.

Provider exception text is never copied into receipts. The public evidence stores bounded reason codes, error type, and a digest. Runtime limits bound provider time, authority-decision time, payload bytes, and observed-state bytes.

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
gymact export-contract ./gymact-contract.json
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
    SQLiteReceiptLedger,
)

AUTHORITY = "urn:example:authority"
SET = "urn:gymact:memory:capability:set"

runtime = GymAct(
    authority_resolver=AllowListAuthorityResolver({AUTHORITY}),
    ledger=SQLiteReceiptLedger("gymact-receipts.sqlite3"),
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
assert await runtime.verify_evidence_chain()
```

`AllowListAuthorityResolver` is a deterministic reference implementation for tests and isolated local gyms. It is explicitly not a substitute for BRCE or another production policy decision point.

## Surfaces

FastAPI:

```python
from gymact.surfaces.fastapi import create_app
app = create_app(runtime)
```

The HTTP surface includes the compiler contract, capability discovery, observations, actions, verification, recovery, receipts, and a public PROV-O evidence projection.

FastMCP:

```python
from gymact.surfaces.fastmcp import create_mcp
mcp = create_mcp(runtime)
```

The MCP transport grants no authority; it submits the same semantic intents as every other surface.

FastStream accepts an externally selected broker, so GymAct does not choose Kafka, NATS, RabbitMQ, Redis, or MQTT on behalf of the caller:

```python
from gymact.surfaces.faststream import create_stream_app
app = create_stream_app(broker, runtime)
```

All surfaces reuse the same Pydantic intents/results and the same runtime. They do not independently reimplement GymAct semantics.

## Semantic authority

`src/gymact/ontology/profile.ttl` contains the application profile and controlled ABox identities. It deliberately defines **zero GymAct OWL/RDFS classes or RDF/OWL properties**. `urn:gymact:*` is reserved for profile resources, ABox identities, SKOS concepts, and SHACL shapes.

Generic lifecycle operations are themselves public `sosa:Procedure` resources. `ProfileAuthority.validate()` runs real pySHACL plus a mechanical zero-custom-TBox gate. `ProfileAuthority.validate_data()` admits extension ABoxes. `ProfileAuthority.validate_capabilities()` projects canonical Pydantic capabilities into SOSA/DCTERMS RDF and validates them through the same SHACL shapes.

## ggen / Rust Gall checkpoint

`ggen/` is intentionally small. CI performs:

```text
packaged profile
  ↓ gymact export-profile
ggen RDF project
  ↓ ggen 26.8.6
generated Rust procedure table
  ↓ rustc --test
executed Gall checkpoint
```

This proves the Python package is not a semantic island without replacing Python-native FastAPI/FastMCP/Typer/FastStream composition with generated boilerplate.

## Release admission

v26.8.7 is releasable only when exact-head CI proves:

- public profile + extension ABoxes parse and SHACL-conform;
- no custom GymAct TBox leaks into profile, shapes, or extension data;
- provider capabilities are validated as public `sosa:Procedure` resources;
- materialization and actuation authority are fail-closed and monotonic;
- write-ahead and terminal receipts form a valid BLAKE3 chain;
- durable SQLite evidence reopens and verifies;
- idempotency and concurrent replay do not duplicate consequences;
- provider time/size failures are bounded and receipted;
- FastAPI executes a real reference episode;
- FastMCP executes in-process through its real Client;
- FastStream executes the broker-neutral lifecycle;
- Typer validates/exports the installed semantic profile and compiler contract;
- ggen manufactures and rustc executes a Rust projection from the same public profile;
- Python 3.11/3.12/3.13 pass tests, coverage, lint, and format gates;
- wheel/sdist metadata and clean-wheel profile resources pass;
- strict docs build passes;
- the production container builds, boots, and answers `/health`;
- dependency closure is resolved into a checked `uv.lock`.

External benchmark integrations retain their own execution standing. Importability is never promoted into scenario-execution standing.
