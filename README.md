# GymAct v26.8.7

GymAct is a Python reference implementation of a **public-semantic execution profile for bounded benchmark and gym worlds**.

Its semantic authority is not a custom GymAct ontology. GymAct composes a W3C `prof:Profile` from PROV-O, P-PLAN, SOSA/SSN, WoT Thing Description, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and Dublin Core Terms. `urn:gymact:*` is reserved for profile/ABox/shape identities, not a competing custom TBox.

Python composes mature libraries directly:

- Pydantic v2 for canonical typed runtime models;
- FastAPI for HTTP/OpenAPI;
- FastMCP for MCP;
- Typer for CLI;
- FastStream for broker-neutral event-driven bindings;
- RDFLib + pySHACL for RDF and conformance;
- RFC 8785 JCS + BLAKE3-256 for cross-runtime evidence identity.

The Rust/WASM path is deliberately separate. `gymact export-bundle` materializes the admitted RDF/SHACL profile plus a self-digested canonical runtime contract for ggen or another compiler to manufacture Rust/WIT/WASM projections.

> **In Python, compose. In Rust, manufacture. At the semantic boundary, verify equivalence.**

## Consequence law

```text
request accepted != world changed != objective verified != benchmark scored

semantic capability identity != provider-local binding

authority_ref != authority decision
```

GymAct v26.8.7 exposes only the generic operations backed by executable evidence today:

```text
discover
materialize
observe
act
verify
checkpoint
restore
teardown
```

A benchmark may add richer lifecycle semantics through data/profiles as executable evidence accumulates; the kernel does not speculate them into existence.

## Bounded actuation

Consequential environments are fail-closed. GymAct invokes an injected `AuthorityResolver` and proceeds only after an explicit positive decision. With no resolver configured, required authority is refused even if the caller supplies an `authority_ref` string.

`RuntimeLimits` bounds authority, materialization, observation, actuation, verification, recovery, teardown, input size, observed-state size, and checkpoint size. Timeout is `BLOCKED`, not success and not authorization denial.

Authority requirements are monotonic in the reference provider: scenario configuration may raise an authority requirement but cannot lower the provider baseline.

Idempotency is semantic:

- same key + same intent → the original result;
- same key + different intent → `REFUSED:IDEMPOTENCY_KEY_CONFLICT`;
- concurrent identical actuation is serialized per episode;
- exact replay does not create another consequential evidence record;
- successful teardown is replayable as the same receipt.

## Evidence

Externally meaningful inputs and evidence use RFC 8785 JSON Canonicalization Scheme. Digests use BLAKE3-256.

Every new materialization, actuation, restore, and teardown disposition carries a `Receipt` and enters a `ReceiptLedger`. The default `MemoryReceiptLedger` is append-only and hash-chained. `SQLiteReceiptLedger` adds transactional local durability with SQLite WAL, `synchronous=FULL`, restart verification, and exact receipt replay.

```python
from gymact import GymAct, SQLiteReceiptLedger

ledger = SQLiteReceiptLedger("./evidence/gymact.sqlite3")
runtime = GymAct(receipt_ledger=ledger)
```

`GymAct.evidence_rdf()` projects execution evidence through PROV-O and independent verification through EARL. This is an evidence representation, not a custom evidence ontology and not a substitute for externally anchored signatures in higher-assurance deployments.

## Quick start

```bash
pip install gymact

gymact version
gymact validate-profile
gymact contract
gymact demo
gymact demo --authority
gymact export-profile ./gymact-profile
gymact export-bundle ./gymact-manufacturing
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

runtime = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
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
assert result.accepted
assert verification.passed
assert runtime.verify_evidence_chain()
```

`AllowListAuthorityResolver` is a deterministic reference implementation for tests and isolated local gyms. It is not a substitute for BRCE or another production policy decision point.

## Native surfaces

All surfaces call the same runtime and Pydantic intents/results; they do not reimplement GymAct semantics.

```python
from gymact.surfaces.fastapi import create_app
from gymact.surfaces.fastmcp import create_mcp
from gymact.surfaces.faststream import create_stream_app

api = create_app(runtime)
mcp = create_mcp(runtime)
stream = create_stream_app(broker, runtime)
```

FastStream accepts the caller's broker so GymAct does not choose Kafka, NATS, RabbitMQ, Redis, or MQTT on the caller's behalf. Transport authentication remains a transport concern; it does not grant world-transition authority.

## Provider plugins

Provider plugin discovery uses the `gymact.providers` entry-point group and is metadata-only. Plugin modules are imported only after an explicit named load request.

```python
from gymact import discover_provider_plugins, load_provider_plugin

available = discover_provider_plugins()
loaded = load_provider_plugin("my-provider")
```

Missing plugins are `UNSUPPORTED`; duplicate identities are `REFUSED`; import or contract failures are `BLOCKED` with hashed error evidence.

## Semantic authority and manufacture

A capability is represented publicly as `sosa:Procedure`. The provider-private binding does not define its meaning. `ProfileAuthority.validate_capabilities()` projects canonical Pydantic capabilities to RDF and admits them through real SHACL.

`build_contract()` publishes the exact operation vocabulary, public semantic dependencies, canonicalization/digest algorithms, and JSON Schemas. The contract is self-digested and independently verifiable.

`export_manufacturing_bundle()` / `gymact export-bundle` emits:

```text
profile.ttl
profile.shacl.ttl
runtime-contract.jcs.json
```

This is the dependency-neutral handoff to ggen/Rust/WIT/WASM.

## Release admission

A v26.8.7 artifact has release standing only when exact-head validation proves:

- public profile and extension ABoxes parse and SHACL-conform;
- zero custom GymAct TBox terms;
- capabilities admit as public `sosa:Procedure` resources;
- materialization and actuation authority fail closed;
- authority requirements cannot be lowered by reference scenario config;
- RFC8785 input admission and BLAKE3 known vectors pass;
- input/state/checkpoint and wall-clock bounds fail safely;
- idempotency/concurrent replay cannot duplicate consequences;
- in-memory and SQLite evidence chains verify, including SQLite restart replay;
- PROV/EARL evidence projection remains distinct from benchmark scoring;
- FastAPI, FastMCP, FastStream, and Typer execute their real contracts;
- Python 3.11/3.12/3.13 pass tests, coverage, lint, and format gates;
- wheel/sdist metadata passes and a clean wheel can validate/export its semantic and manufacturing bundles;
- strict docs and the production container build and probe successfully;
- CI captures the tested dependency resolution as an artifact.

The repository is a reusable library, so dependency ranges remain package metadata and downstream applications own their deployment lock. CI's resolved lock is test evidence rather than a lock imposed on downstream consumers.

External benchmark integrations retain their own execution standing. Importability is never promoted into scenario-execution standing.
