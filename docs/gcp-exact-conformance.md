# GCP exact conformance

GymAct treats **"simulate GCP exactly"** as a falsifiable external-equivalence claim, not as a claim to reproduce Google's private implementation.

## Admission boundary

The admitted public contract is built from Google-published and Google-observed sources. The first executable source is the Google APIs Discovery Service directory. Every API/version in that directory is fetched, every nested resource method is flattened into a deterministic identity, and every published JSON schema is canonicalized and digested. No preferred-version shortcut is allowed by default.

The census is only the API coordinate system. Behavioral standing requires differential evidence from a real GCP project for the same admitted method and state. The target evidence set includes:

- Google APIs Discovery Service: API versions, REST methods, paths, request/response schemas, OAuth scopes, and documentation links;
- Google Cloud Service Usage: which services are actually available/enabled for the subject project;
- Cloud Asset Inventory: resource state, history, relationships, IAM and organization-policy projections where supported;
- Cloud Audit Logs: observed consequential calls and their externally visible outcomes;
- long-running operations: operation creation, polling, terminal state, errors, cancellation/deletion behavior where exposed;
- IAM: permission-denied behavior and policy-dependent visibility;
- quotas and documented limits: admitted error classes and retry-visible behavior;
- service-specific REST/RPC documentation and protobuf descriptors where a service publishes semantics not carried by Discovery;
- documented regional/global endpoint behavior and lifecycle constraints;
- live differential probes against real GCP, with receipts for both real and simulated executions.

Anything not covered by a published contract or an empirical observation remains `UNKNOWN`. `UNKNOWN` is never promoted to exactness.

## Exactness law

For an admitted contract set `C` and evidence set `E`:

```text
EXACT(C, E) :=
  C is non-empty
  AND every admitted method has evidence
  AND every method disposition is ALIVE
  AND there are no extra simulator-only methods
  AND there are no silent exclusions
```

A method is `ALIVE` only when the simulator and real GCP executions match for the admitted observation projection. Schema compatibility alone is not behavioral equivalence.

## DfCM decomposition

The GCP surface is not implemented as one giant handwritten emulator. DfCM preserves the maximum lawful decomposition:

```text
Google contract sources
        |
        v
contract census -----> RDF ABox projection
        |
        v
method/schema partitions
        |
        +--> generated request domains
        +--> generated state-transition probes
        +--> generated negative/IAM/quota probes
        +--> generated LRO probes
        |
        v
real GCP execution ---- paired ---- GymAct simulation
        |                              |
        +----------- receipts --------+
                       |
                       v
                differential verifier
                       |
                       v
        UNKNOWN / PARTIAL_ALIVE / ALIVE / BLOCKED /
        UNSUPPORTED / typed REFUSED
```

One failing service or method does not invalidate the rest of the graph; it creates an explicit topology boundary. The aggregate GCP claim remains non-exact until every admitted boundary is closed.

## Current executable layer

`gymact.gyms.gcp_exact` provides:

- `load_discovery_census()` — live, credential-free enumeration of every Discovery API/version;
- `flatten_discovery_document()` — deterministic recursive method/schema extraction;
- `build_contract_rdf()` — public-vocabulary RDF projection using DCAT, DCTERMS and SKOS with `urn:gymact:gcp:*` only as ABox identities;
- `GcpCoverageReport.evaluate()` — fail-closed standing over the complete admitted method set.

This layer is **PARTIAL_ALIVE by design** until live GCP differential execution is connected and the complete admitted census closes. A passing unit test proves the census/standing machinery, not GCP behavioral equivalence.

## Next closure edges

The next implementation edges are mechanical and independently falsifiable:

1. ingest Google service/RPC descriptors not represented in Discovery;
2. bind Service Usage to a subject project and materialize the enabled/available service set;
3. capture pre/post Cloud Asset Inventory projections for consequential probes;
4. bind Audit Log entries and long-running operations to the same actuation receipt;
5. generate request domains and negative cases from schemas, IAM metadata and documented limits;
6. execute paired real/simulator probes through BRCE;
7. emit one coverage record per admitted method and fail the aggregate exactness gate on any non-`ALIVE` disposition;
8. replay the evidence corpus deterministically and diff simulator revisions against the last admitted GCP corpus.

The crown condition is not "the simulator has many GCP features." It is a machine-readable report proving **zero uncovered admitted contract units** for a declared GCP contract snapshot and observation projection.
