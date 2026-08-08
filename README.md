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
