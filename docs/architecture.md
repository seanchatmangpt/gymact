# GymAct architecture

GymAct treats benchmark actuation as execution against a bounded world, not as an adapter-specific command API.

## Semantic authority

The package owns an application profile and ABox identities, not a custom ontology TBox. Public ontologies provide the semantics:

- PROF: application-profile identity;
- PROV-O: entities, activities, agents, causal history, bundles;
- P-PLAN: prospective plan/step structure;
- SOSA/SSN: observation, actuation, and `sosa:Procedure` capabilities;
- WoT TD/TM: virtual worlds and interaction affordances;
- ODRL: permissions, prohibitions, duties, constraints;
- SHACL: executable structural/pre/postcondition constraints;
- EARL: verification assertions/results;
- DQV + QUDT: metrics and quantitative values;
- DCAT + SKOS + OWL-Time + DCTERMS: datasets, taxonomies, temporal and descriptive metadata.

`urn:gymact:*` resources are instances, concepts, shapes, and profile identifiers only.

A provider capability is a canonical Pydantic realization of a public `sosa:Procedure`:

```text
Capability.iri          -> RDF subject
Capability.title        -> dct:title
Capability.consequence  -> dct:type READ/DO SKOS concept
Capability.binding      -> provider-private implementation detail
```

The binding is intentionally not semantic authority. Two providers may bind the same public capability identity differently.

## Python composition

```text
semantic profile
      |
      v
canonical Pydantic models
      |
 +----+------+---------+----------+
 |           |         |          |
FastAPI   FastMCP    Typer    FastStream
OpenAPI     MCP       CLI      brokers
```

These are external Python dependencies, not ggen-produced reimplementations. Provider integrations may also be installed as `gymact.providers` entry points, but discovery is metadata-only and never imports plugin code. Loading a provider is an explicit operation.

## Runtime boundary

```text
discover -- registry inspection; not part of an episode's own trajectory

MaterializationIntent
       |
       v
RFC 8785 admissibility + input bound
       |
       v
EnvironmentProvider -- authority when provider declares setup consequential
       |
       v
Environment -- capabilities() -- real SHACL admission
       |
       +-- observe
       +-- actuate(Capability, payload)
       +-- verify
       +-- checkpoint / restore
       +-- teardown
```

`gymact.models.Operation` names these as `discover, materialize, observe, act, verify,
checkpoint, restore, teardown` -- 8 values, deliberately not the `configure`/`reset`/`start`/
`score` some earlier design sketches described (see that enum's own docstring for the Reduce
rationale: `materialize` already subsumes configure/reset/start for the current provider set,
and `VerificationResult.passed` already serves as the pass/fail signal a separate `score`
would add).

Materialization and actuation have separate idempotency domains. A materialization failure never becomes an `Episode`; an admitted materialization returns an initial independent observation and receipt. Successful teardown is retained as a tombstone receipt so transport retries cannot cause a second teardown.

`gymact.process.ConformanceChecker` replays a real episode's `Receipt.operation` sequence
against `gymact.process.LIFECYCLE` -- a hand-checkable transition table over `Operation`, not
a parallel event-log representation (it operates directly on `Receipt`s the runtime already
returns).

## Real gym providers

Several real `EnvironmentProvider` implementations exist in `gymact.gyms`, each driving a
genuinely real external collaborator (zero mocks anywhere in `src/` or `tests/`):

| Provider | Real collaborator |
|---|---|
| `gyms.cube_counter.CubeCounterProvider` | an in-process CUBE reference task (`counter_cube` package) -- no Docker, no network, no subprocess |
| `gyms.cube_container_counter.CubeContainerCounterProvider` | a real local Docker daemon provisioning a real container running CUBE's `toy_benchmark` example |
| `gyms.ggen_legacy.GgenLegacyVerifierProvider` | a real subprocess of the compiled `ggen-v26-8-1-verifier` binary against a real `~/ggen-legacy` checkout |
| `gyms.discovered.GenericDiscoveredProvider` | a generic actuator: runs an LLM-proposed, bounded subprocess recipe (`command`/`cwd`/`timeout_seconds`/`success_markers`) against an arbitrary checked-out repo, instead of a hand-written adapter per benchmark subject |
| `gyms.gymnasium_env.GymnasiumProvider` | a real, already-installed `gymnasium` package's `Env` (default `CartPole-v1`) -- no vendored agentgym, no subprocess |
| `gyms.mcp_client_session.McpClientSessionProvider` | a real `fastmcp.Client` session against a real subject `FastMCP` server (defaults to `gymact.surfaces.fastmcp.create_mcp()`), driven only through `list_tools()`/`call_tool()` -- no simulated tool catalog or canned result |
| `gyms.kubernetes_reconciliation.KubernetesReconciliationProvider` | a real local Kubernetes cluster (`kind`/`k3d`/colima `--kubernetes`) via real `kubectl` subprocess calls -- `verify()` polls real cluster-observed pod phase, not `kubectl apply`'s exit code |
| `gyms.terraform_plan.TerraformPlanProvider` | a real `terraform`/`tofu` subprocess running `init -backend=false` and `plan` against a real checked-out Terraform configuration directory -- structurally no `apply`/`destroy` path |
| `gyms.terraform_docker_apply.TerraformDockerApplyProvider` | a real local `terraform`/`tofu` binary running `apply`/`destroy` against a hand-authored, checked-in Terraform config (`gyms/fixtures/terraform_docker/main.tf`) that provisions exactly one pinned `docker_image`/`docker_container` on colima's real local Docker daemon -- no cloud provider, no cloud credentials |

Each of these claims a `gymact.standing.require_standing` standing string (e.g.
`"LOCAL_GYM:cube-counter"`). The real thing is the default: if the real collaborator is
unavailable, the run fails loudly unless `GYMACT_ALLOW_DEGRADED_STANDINGS` explicitly lists
that standing (or `"*"`) -- a skip must be opted into, never silently defaulted.

## OCEL 2.0 export

`GymAct.episode_receipts()`/`GymAct.episode_ocel_log()` turn any episode's real receipt trail
(every lifecycle call routes through the kernel's single `_record` chokepoint, which also
feeds the tamper-evident receipt ledger) into an OCEL 2.0 log via `gymact.ocel.receipts_to_ocel`;
`gymact.ocel.validate_ocel_log` checks it against the real vendored OCEL 2.0 JSON Schema.
Exported logs have been independently cross-validated against a real `wpm receipt verify-ocel2`
subprocess (see `~/wasm4pm`).

The FastMCP surface additionally exposes a read-only `probe_repo` tool (README/pyproject/
setup.py plus a truncated top-level listing) -- it never gains shell/exec access; actual
command execution stays behind `actuate()`/authority.

## Bounded consequence

Every external boundary has a wall-clock limit. Inputs, observations and checkpoints have serialization-size limits. Timeout is `BLOCKED`: it is neither authorization denial nor proof that a remote system produced no effect.

## Consequence law

```text
accepted request
      !=
observed effect
      !=
verified objective
      !=
benchmark score
```

A provider acknowledgement cannot manufacture verification. A semantic capability with READ consequence cannot be smuggled through the actuation method. Benchmark scoring is an explicit `Scorer` policy above `VerificationResult`; the generic runtime does not manufacture a score from actuation success.

## Authority

`authority_ref` is only an identifier supplied with an intent. When the provider/environment declares authority required, GymAct sends the exact semantic operation to an injected `AuthorityResolver`. The default resolver denies. A positive decision may carry a separate evidence reference that is bound into the receipt.

Authority requirements are monotonic in the reference provider: scenario configuration can raise the requirement but cannot lower the provider baseline. Third-party providers remain responsible for truthfully declaring their own consequential boundary; their capabilities are admitted through the semantic profile but are not trusted merely because they import.

## Evidence

GymAct canonicalizes externally meaningful JSON with RFC 8785 JCS and hashes it with BLAKE3-256. This creates an independently implementable digest contract across Python, Rust, WASM and JavaScript rather than relying on Python-specific JSON serialization.

New materialization, actuation, restore and teardown receipts enter an injected `ReceiptLedger`. The reference in-memory ledger is hash-chained. `SQLiteReceiptLedger` provides a dependency-free durable option using SQLite WAL, `synchronous=FULL`, transactional writer serialization, startup chain verification and restart replay.

```text
Receipt n-1 digest
       |
       v
RFC8785(Receipt n)
       |
       v
BLAKE3-256
       |
       v
EvidenceRecord n
```

Exact idempotent replay returns the original result and does not add a second consequential record. `evidence_rdf()` projects receipts through PROV-O and independent verification assertions through EARL; GymAct does not invent a custom evidence ontology.

## Rust/WASM manufacture boundary

`build_contract()` exposes a self-digested cross-runtime contract containing the exact eight evidence-backed operations, public semantic dependencies and Pydantic JSON Schemas. `export_manufacturing_bundle()` emits:

```text
profile.ttl
profile.shacl.ttl
runtime-contract.jcs.json
```

That bundle is the deterministic input for ggen or another compiler. ggen may manufacture static Rust/WIT/WASM types, dispatch tables, predicates, authority gates, verifier bindings and fixtures. The Python library remains the ecosystem-native reference implementation; the Rust implementation is an independent projection suitable for observational-equivalence tests.

The design rule is therefore:

> In Python, compose. In Rust, manufacture. At the semantic boundary, verify equivalence.
