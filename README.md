# GymAct

GymAct is the lawful executable-world layer for AutoFDE: a public-semantic runtime for turning admitted computational intent into independently verified consequence.

The v26.8.7 production architecture is **Design for Combinatorial Maximum (DCM)**. GymAct does not choose a planner/provider/tool first and then guard that choice. It preserves the maximum bounded set of lawful reversible possibilities before any irreversible selection:

```text
public RDF possibility graph
  -> SHACL admission
  -> lossless runtime projection
  -> structural scan
  -> complete maximal proven-reversible closure
  -> applicability filter
  -> empirical/Pareto retrieval when useful
  -> explicit semantic irreversible cut
  -> fresh authority admission
  -> BRCE
  -> consequence
  -> independent observation
  -> verification
  -> closure-bound receipt
  -> replay
```

The design invariant is **zero unreceipted actuation**. Planner output, model output, graph queries, caches, compiled routes, MCP calls and transport payloads are powerless candidates. Consequential DO is a separately admitted transition.

## Design for Combinatorial Maximum

The canonical public API is `gymact.dcm`. The possibility graph is the decision authority; Python objects are runtime projections of public RDF semantics.

DCM preserves alternatives across planners, providers, parameterizations, effectors, verifiers, policies and controllers. A failed edge is recorded as topology and does not invalidate siblings. Only edges mechanically proven `REVERSIBLE` enter reversible closure:

```text
COMPENSATABLE != REVERSIBLE
UNKNOWN != REVERSIBLE
IRREVERSIBLE != REVERSIBLE
```

Resource bounds are explicit. If closure is truncated, truncation is evidence and an irreversible cut is refused.

Every DO edge must carry powerless identity for the exact action, subject, capability, verifier and expected effect. Exploration never traverses DO. An explicit cut then binds the exact graph, complete closure, path, DO morphism, semantic consequence, prepared intent, grant, selector and selection evidence before BRCE can execute.

Consequential receipts preserve the same decision identity, so replay can detect changed graph topology, changed closure computation or a changed irreversible choice even if the final external API call looks identical.

See [`docs/combinatorial-maximum.md`](docs/combinatorial-maximum.md) and the machine law inventory at `src/gymact/schemas/dcm-v26.8.7.json`.

## Public semantic authority

GymAct prefers public vocabularies rather than a proprietary ontology runtime. The semantic profile uses public standards including PROV-O, P-PLAN, SOSA/SSN, ODRL, SHACL, SKOS, DCTERMS, EARL, DQV, QUDT, DCAT and OWL-Time where applicable.

`urn:gymact:*` resources are reserved for profile resources, ABox identities, SKOS concepts and SHACL shapes. The DCM RDF projection uses public predicates/classes; GymAct does not need a proprietary RDF/OWL TBox to represent the possibility graph.

## Authority and consequence

Production surfaces instantiate `ProductionGymAct`. Direct raw `act()` is a typed receipted refusal. The canonical production path is a DCM-selected, cut-bound request into BRCE.

These are deliberately different claims:

```text
command accepted
!= action performed
!= world changed
!= desired postcondition
!= independently verified objective
```

A request naming an authority reference does not grant that authority. CLI authority is supplied through a separate operator-controlled source; REST/MCP/event transports cannot install or widen the runtime authority resolver.

## Cognition compilation

Repeated successful cognition is compiled into a **graph route**, not cached execution authority:

```text
cold reasoning
  -> admitted possibility graph
  -> reversible path + DO frontier
  -> witnessed receipts
  -> compiled graph route
  -> re-admission against current graph
  -> fresh irreversible cut + authority
```

This is the route from cold -> warm -> hot operation while preserving identical or stronger consequence law.

## Empirical selection

Historical performance cannot create applicability. The canonical empirical possibility index requires:

1. the current set of lawfully eligible combination identities;
2. a valid receipt ledger;
3. witnessed standing for each empirical record;
4. verified consequence before an `ALIVE` record may enter ranking.

Only then is a Pareto frontier computed over cost, wall time, compute, human intervention, risk, verification confidence and value.

## Providers and interfaces

GymAct supports a generic provider SPI and real provider families for bounded local and network worlds, with browser/cloud/Kubernetes/IaC/SaaS/robotics/OT classes represented through provider/profile extension rather than by flattening their physics.

Public surfaces include Python/Pydantic, CLI/Typer, REST/OpenAPI/FastAPI, MCP/FastMCP, FastStream/A2A-style event transport, RDF/JSON-LD, OCEL and planner/process projections.

Compatibility surfaces from the pre-DCM runtime remain where needed for migration, but they are not canonical production decision authority.

## Evidence standing

GymAct distinguishes implementation from witnessed execution. DCM source implementation is `STRUCTURAL` until the full exact-subject chain executes:

```text
RDF admission
-> complete maximal closure
-> semantic frontier
-> explicit cut
-> real consequence
-> independent verification
-> closure-bound receipt
-> exact replay
```

Source publication, importability, mocks, or earlier provider executions do not establish DCM `ALIVE`. The machine execution overlay is `src/gymact/schemas/dcm-evidence-v26.8.7.json`.

## Development

The repository uses Python 3.11-3.13, Pydantic, RDFLib/pySHACL, FastAPI, FastMCP, FastStream, Typer, BLAKE3/RFC8785 evidence and strict tests. The release contract also checks packaging, documentation, lock resolution and the production container.

Use:

```bash
gymact dcm-status
gymact dcm-requirements
gymact explore <court-request.json>
gymact execute <request.json> --authority-file <operator-authority.json>
```

`gymact execute` is DCM-first. The hidden `execute-admitted` command is compatibility only.

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

The FastMCP surface also exposes `probe_repo`, a read-only repository prober (README/
pyproject/setup.py plus a truncated top-level listing). It has no shell/exec access -- actual
command execution stays behind `actuate()`/authority, unaffected by this tool's presence.

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

## Real gym providers

Beyond `MemoryProvider`, `gymact.gyms` has several providers that each drive a genuinely real
external collaborator -- no mocks anywhere in `src/` or `tests/`:

- `cube_counter.CubeCounterProvider` -- an in-process CUBE reference task (`counter_cube`).
- `cube_container_counter.CubeContainerCounterProvider` -- a real Docker container running
  CUBE's `toy_benchmark` example.
- `ggen_legacy.GgenLegacyVerifierProvider` -- a real subprocess of the compiled
  `ggen-v26-8-1-verifier` binary against a real `~/ggen-legacy` checkout.
- `gymnasium_env.GymnasiumProvider` -- a real, already-installed `gymnasium` package's `Env`
  (default `CartPole-v1`).
- `mcp_client_session.McpClientSessionProvider` -- a real `fastmcp.Client` session against
  a real subject `FastMCP` server (defaults to `gymact.surfaces.fastmcp.create_mcp()`),
  driven only through `list_tools()`/`call_tool()`.
- `kubernetes_reconciliation.KubernetesReconciliationProvider` -- a real local Kubernetes
  cluster (`kind`/`k3d`/colima `--kubernetes`) via real `kubectl` subprocess calls; `verify()`
  polls real cluster-observed pod phase rather than trusting `kubectl apply`'s exit code.
- `terraform_plan.TerraformPlanProvider` -- a real `terraform`/`tofu` subprocess running
  `init -backend=false` and `plan` (never `apply`/`destroy`) against a real checked-out
  Terraform configuration directory.
- `terraform_docker_apply.TerraformDockerApplyProvider` -- a real `terraform`/`tofu` binary
  running `apply`/`destroy` against a hand-authored, checked-in local-only Docker config
  (`gyms/fixtures/terraform_docker`), against colima's real local Docker daemon.
- `vendor_benchmarks.VendorBenchmarkProvider` -- one exact-pinned provider per vendor
  benchmark in AutoFDE Lab's `docs/papers/gym-lock.ttl` (52 vendors: AgentBench,
  SWE-bench, Cybench, Terminal-Bench, WebArena, and 47 others); each provider only
  materializes after the real vendor checkout's Git HEAD equals its pinned revision,
  and every native command runs cwd-bound to that checkout with no shell.

- `vendor_benchmarks.VendorBenchmarkProvider` -- one provider per AutoFDE Lab
  `docs/papers/gym-lock.ttl`-pinned vendor checkout (52 exact-pinned benchmark repos);
  materializes only when the real checkout's Git HEAD equals the pinned revision, and
  re-checks the pin both before and after running a real cwd-bound, no-shell subprocess.

Each claims a `gymact.standing.require_standing` standing (e.g. `"LOCAL_GYM:cube-counter"`):
if its real collaborator is unavailable, the run fails loudly unless
`GYMACT_ALLOW_DEGRADED_STANDINGS` explicitly permits degrading it -- a skip must be opted
into, never a silent default.

`gymact.gyms.discovered.GenericDiscoveredProvider` generalizes this further: one provider
that runs an LLM-proposed, bounded subprocess recipe against an arbitrary checked-out repo,
rather than a hand-written adapter per benchmark subject. `scripts/discover_and_actuate.py`
is the end-to-end probe -> propose -> actuate -> OCEL driver; `scripts/ocel_standing.py`
derives actuation standing purely from the resulting on-disk OCEL log (schema validation +
`ConformanceChecker` replay + explicit ALIVE/solved check), never from script narration.

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
