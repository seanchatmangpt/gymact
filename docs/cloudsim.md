# CloudSim: zero-spend global cloud worlds

CloudSim is GymAct's finite semantic control-plane simulator for AWS-, Azure-, and
GCP-shaped consequential worlds. It exists to run large cloud benchmarks, self-play,
failure injection, planning experiments, and Fortune-scale topology scenarios without
creating real cloud resources or requiring cloud credentials.

## Constitutional boundary

CloudSim **does not claim complete SDK or HTTP wire compatibility** with AWS, Azure,
or Google Cloud. Instead it normalizes the part cloud gyms need for consequential
reasoning:

```text
CloudOperation =
  Cloud × Service × VendorOperation × SemanticEffect × Scope × Region
  × ResourceType × ResourceIdentity × Properties × Dependencies × VisibilityDelay
```

The service and vendor-operation fields are intentionally open-world strings. A new API
operation is data, not a new simulator branch. The finite effect algebra is:

```text
CREATE | UPDATE | DELETE | BIND | UNBIND | TRANSITION | INVOKE
```

That gives the simulator a small executable kernel while preserving an arbitrarily large
vendor API namespace. Provider-specific Smithy/OpenAPI/Discovery adapters can lower real
API definitions into this basis later without becoming competing world truth.

## Global topology

The default world admits three scopes (`prod`, `shared`, `security`) and six global
regions per cloud. Tests can materialize any larger bounded topology as ordinary config.
Topology is data, so increasing accounts/subscriptions/projects, regions, services, or
resources does not create a new execution path.

## Failure and systems semantics

The state machine includes deterministic resource identity, dependencies, lifecycle
transitions, IAM-like bindings, quotas, injected failures, a logical clock, delayed
visibility/eventual consistency, checkpoint/restore, and an append-only event stream.
These are simulation semantics, not claims about every vendor's precise control-plane
implementation.

## Zero-spend law

The CloudSim package imports no `boto3`, `botocore`, Azure SDK, or Google Cloud client.
It contains no cloud endpoints and consumes no cloud credentials. CI explicitly clears
common cloud credential variables and runs the simulator through the real GymAct runtime.

Simulation does not weaken authority. Every CloudSim capability has `DO` consequence,
materialized environments require authority by default, and the normal GymAct runtime
mints the receipt. Production use still belongs behind `ProductionGymAct` and BRCE; the
simulator is a world provider, never a second actuation authority.

## Seed service basis

`SERVICE_FAMILIES` names 62 common service families spanning identity/organization,
network, compute, storage, databases, serverless, messaging, keys/secrets, containers,
DNS/edge, monitoring, analytics/data, ML, and backup. The catalog is a discovery seed,
not an allow-list: a previously unseen service string must execute through the same
finite algebra without source changes.

## Acceptance

The repository-native proof must demonstrate all of the following with real objects and
no interaction-verifying test doubles:

- ontology/capability parity;
- AWS, Azure, and GCP share the same finite world algebra;
- no cloud SDK imports or credentials are required;
- missing authority leaves state unchanged and produces a refusal receipt;
- admitted actions across multiple service families mutate only in-memory state and are
  receipted;
- an unknown service name works without adding a code path;
- eventual consistency, injected failure, quota, dependency, and recovery semantics are
  deterministic;
- CI records the exact commit and the zero-live-cloud boundary.
