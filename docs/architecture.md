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

These are external Python dependencies, not ggen-produced reimplementations.

## Runtime boundary

```text
discover -- registry inspection; not part of an episode's own trajectory

MaterializationIntent
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

Three real `EnvironmentProvider` implementations exist in `gymact.gyms`, each driving a
genuinely real external collaborator (zero mocks anywhere in `src/` or `tests/`):

| Provider | Real collaborator |
|---|---|
| `gyms.cube_counter.CubeCounterProvider` | an in-process CUBE reference task (`counter_cube` package) -- no Docker, no network, no subprocess |
| `gyms.cube_container_counter.CubeContainerCounterProvider` | a real local Docker daemon provisioning a real container running CUBE's `toy_benchmark` example |
| `gyms.ggen_legacy.GgenLegacyVerifierProvider` | a real subprocess of the compiled `ggen-v26-8-1-verifier` binary against a real `~/ggen-legacy` checkout |
| `gyms.discovered.GenericDiscoveredProvider` | a generic actuator: runs an LLM-proposed, bounded subprocess recipe (`command`/`cwd`/`timeout_seconds`/`success_markers`) against an arbitrary checked-out repo, instead of a hand-written adapter per benchmark subject |

Each of the first three claims a `gymact.standing.require_standing` standing string (e.g.
`"LOCAL_GYM:cube-counter"`). The real thing is the default: if the real collaborator is
unavailable, the run fails loudly unless `GYMACT_ALLOW_DEGRADED_STANDINGS` explicitly lists
that standing (or `"*"`) -- a skip must be opted into, never silently defaulted.

## OCEL 2.0 export

`GymAct.episode_receipts()`/`GymAct.episode_ocel_log()` turn any episode's real receipt trail
(every lifecycle call routes through a single `_emit` chokepoint) into an OCEL 2.0 log via
`gymact.ocel.receipts_to_ocel`; `gymact.ocel.validate_ocel_log` checks it against the real
vendored OCEL 2.0 JSON Schema. Exported logs have been independently cross-validated against
a real `wpm receipt verify-ocel2` subprocess (see `~/wasm4pm`).

The FastMCP surface additionally exposes a read-only `probe_repo` tool (README/pyproject/
setup.py plus a truncated top-level listing) -- it never gains shell/exec access; actual
command execution stays behind `actuate()`/authority.

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

A provider acknowledgement cannot manufacture verification. A semantic capability with READ consequence cannot be smuggled through the actuation method.

## Authority

`authority_ref` is only an identifier supplied with an intent. When the provider/environment declares authority required, GymAct sends the exact semantic operation to an injected `AuthorityResolver`. The default resolver denies. A positive decision may carry a separate evidence reference that is bound into the receipt.

## Rust/WASM bridge

The exact packaged RDF/SHACL profile can be exported for ggen. ggen may manufacture static Rust/WIT/WASM types, dispatch tables, predicates, authority gates, verifier bindings, and fixtures. The Python library remains the ecosystem-native reference implementation; the Rust implementation is an independent projection suitable for observational-equivalence tests.
