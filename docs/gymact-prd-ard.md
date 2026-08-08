# GymAct PRD / ARD — Crown execution substrate

Version: 26.8.7  
Status: architectural constitution  
Canonical decision architecture: **Design for Combinatorial Maximum (DCM)**

GymAct is the universal effector layer through which admitted AutoFDE intent encounters
consequential reality. It is not an agent framework and it is not a generic tool router.
Its job is to make execution lawful, measurable, falsifiable, independently verifiable,
replayable and progressively compilable out of repeated cognition.

The production causal chain is:

```text
O -> O* -> public possibility graph
  -> SHACL admission
  -> structural scan
  -> complete maximal proven-reversible closure
  -> applicability
  -> empirical/Pareto retrieval where useful
  -> explicit semantic irreversible cut
  -> fresh authority admission
  -> BRCE
  -> E
  -> O'
  -> V
  -> R
  -> replay/reuse
```

The detailed DCM law is canonical in `docs/combinatorial-maximum.md` and
`src/gymact/schemas/dcm-v26.8.7.json`.

## 1. Product objective

GymAct SHALL expose heterogeneous executable worlds through a common semantic contract
without pretending their physics are identical.

Target provider families include browser, Kubernetes, cloud, infrastructure as code,
filesystem, Git/GitHub, databases, SaaS APIs, MCP, A2A, BPMN/workflow engines,
robotics, industrial/OT protocols where safely available, benchmark environments,
simulations and enterprise application APIs.

A provider can be discoverable or structurally valid without being `ALIVE`. Every
provider seeking `ALIVE` SHALL execute against a real compatible subject.

## 2. Design for Combinatorial Maximum

GymAct SHALL preserve the maximum bounded set of lawful reversible possibilities before
irreversible selection. The possibility graph is canonical decision authority; Python
models, transports and generated artifacts are projections.

Conceptually:

```text
P = D × Pi × Theta × E × V × A × C × ...
```

A compact layered graph SHOULD preserve the product of possible routes without eagerly
materializing every Cartesian tuple as a separate runtime object.

The following are hard distinctions:

```text
REVERSIBLE != COMPENSATABLE
REVERSIBLE != UNKNOWN
failed(edge) != failed(graph)
SELECT != CONSTRUCT != DO
candidate != authority
```

Resource bounds SHALL be explicit. A truncated closure SHALL NOT authorize an
irreversible cut.

## 3. Semantic consequential frontier

Exploration never traverses DO. A consequential morphism remains visible topology but
cannot become an admitted DO frontier unless it binds the exact powerless semantic
identity of:

- action;
- subject;
- capability;
- verifier;
- expected-effect digest.

The cut SHALL re-check the semantic binding against the exact ActionDefinition and
PreparedAction. An unrelated DO edge cannot serve as a ceremonial authorization edge.

## 4. Irreversible cut

Before BRCE receives a canonical production request, GymAct SHALL create a content-bound
selection identity over:

- possibility graph digest;
- complete exploration/closure digest;
- reversible path identity;
- DO morphism identity;
- semantic consequence identity;
- prepared action digest;
- execution grant digest;
- selector identity;
- selection basis/evidence.

The canonical production request is `CombinatorialBrokerRequest`. The historical
single-action `BrokerRequest` is compatibility only.

## 5. Zero unreceipted actuation

No production-capable operation may alter external state except through an admitted
authority boundary.

```text
DO => DCM cut => BRCE
```

Every admitted actuation SHALL yield a cryptographically bound receipt or explicit
uncertainty/refusal disposition.

## 6. Candidate is not authority

Planner output, model output, optimizer output, workflow output, graph query output,
compiled graph routes, MCP requests and transport payloads are powerless candidates.

A request may name an `authority_ref`; it may not install or widen the runtime's
authority resolver. Authority must come from an independently configured resolver.

## 7. Acknowledgement is not effect

GymAct SHALL preserve distinct claims for:

```text
command accepted
!= action performed
!= world changed
!= desired postcondition
!= verified objective
```

An executor saying “success” is not sufficient verification where an independent
observation is technically possible.

## 8. Public ontology operating model

The public semantic graph SHALL prefer PROV-O, P-PLAN, SOSA/SSN, ODRL, SHACL, SKOS,
DCTERMS, QUDT, OWL-Time, EARL, DQV, DCAT and WoT semantics where applicable.

GymAct-owned RDF/OWL predicates/classes are forbidden unless public vocabulary cannot
lawfully represent the requirement. `urn:gymact:*` is reserved for profile resources,
ABox identities, SKOS concepts and SHACL shapes.

The DCM graph projection currently uses public RDF/PROV/DCTERMS/SKOS/SHACL semantics
and SHALL round-trip losslessly to the runtime projection at the exact graph digest.

## 9. Planner / provider maximalism

No solver, provider, verifier or controller SHALL replace another lawful alternative
merely because it is newer or locally faster.

Applicability is evaluated before ranking. Historical performance cannot manufacture
current applicability.

The canonical empirical possibility index SHALL require receipt-backed witnessed
records. `ALIVE` empirical records require a verified consequence receipt. Only current
eligible identities are admitted to Pareto comparison.

## 10. Structural scan and indexed retrieval

Cheap structural characteristics SHALL be extracted before expensive interpretation.
The structural signature SHOULD cover topology, branching, cycles, object/morphism
classes, reversibility, standing and SELECT/CONSTRUCT/DO phase counts.

Semantically distinct graphs may share a structural key while retaining separate exact
content identities.

## 11. Cognition compilation

Repeated successful reasoning SHALL be examined for compilable graph structure.
The canonical HOT artifact is a graph route:

```text
(graph identity, reversible path, DO frontier, witnessed receipts)
```

A route is re-admitted against the current graph. It contains no live authority. A fresh
irreversible cut and fresh authority admission remain required.

Legacy candidate recipes are compatibility only and SHALL NOT outrank the canonical
graph-route representation.

## 12. Receipts and provenance

Consequential receipts SHALL bind decision topology as well as effect:

```text
R = H(G, closure, path, DO, selection, authority, effect, O', V, parents)
```

The public evidence graph SHALL connect the receipt to the selection, graph, exact
closure, path, morphism and selection-basis evidence through public PROV/DCTERMS
relations.

## 13. Replay

Replay SHALL distinguish evidence replay, verifier replay, simulation replay and live
re-execution. Replay must not silently actuate.

When exact DCM identity is expected, missing graph/closure/path/morphism/selection
identity is evidence loss, not a wildcard. Changed identity is drift.

## 14. Uncertain execution

Lost acknowledgement after possible actuation SHALL NOT be blindly retried:

```text
UNCERTAIN -> RECONCILE -> OBSERVE -> DECIDE
```

Unknown idempotency requires stricter admission.

## 15. Protocol projections

CLI, REST, MCP and event transports SHALL preserve the same causal phases:

```text
CONSTRUCT -> MAXIMAL_CLOSURE -> EXPLICIT_CUT -> DCM_DO
```

REST canonical DO: `/episodes/{episode_id}/actions/selected`.
The older `/actions/admitted` and raw `/actions` routes are compatibility/deprecated.

MCP retains one `act` transport but makes its phase explicit: candidate, court,
selected-cut DO, compatibility request or legacy refusal path.

## 16. Physical and edge execution

Robotics, OT and edge controllers require bounded safety envelopes, safe-state identity,
verifier identity, operation allowlists, rate/duration bounds and explicit policy for
irreversible behavior.

A manifest cannot self-declare physical `ALIVE`. Real subject evidence is required.

## 17. Process evidence

Execution receipts SHALL remain convertible to OCEL-compatible evidence for conformance,
bottleneck, throughput, waiting time, remaining-time, handover, drift, rework and
failure-cluster analysis.

POWL v2 remains the preferred partial-order process representation where supported;
wasm4pm may provide an independent execution/verification substrate where available.

## 18. Self-play and mutation testing

The lab SHOULD generate combinatorial valid, boundary, stale, unauthorized, ambiguous,
unsupported, lost-ACK, partial-effect, wrong-effect, delayed-effect, irreversible,
duplicate and replay-mismatch scenarios.

Critical falsifiers include:

1. planner/model output directly actuates;
2. UNKNOWN or COMPENSATABLE enters reversible closure;
3. a failed edge erases siblings;
4. bounds silently prune;
5. a truncated closure selects DO;
6. a DO edge lacks exact semantic consequence identity;
7. applicability is skipped before ranking;
8. empirical ranking accepts unwitnessed ALIVE data;
9. a transport installs authority from request payload;
10. a cut is absent or does not bind exact graph/closure/path/DO identity;
11. acknowledgement is accepted as verified consequence;
12. replay accepts missing/drifted DCM identity;
13. mocks establish production ALIVE;
14. generated code becomes canonical over the public graph.

## 19. GALL checkpoints

The existing CP0–CP16 GALL namespace remains closed for compatibility and release
accounting. DCM end-to-end standing is maintained separately in
`src/gymact/schemas/dcm-evidence-v26.8.7.json` rather than inventing a pseudo-CP17.

Prior real provider execution establishes only the exact slices that executed. It does
not retroactively establish DCM end-to-end `ALIVE` after the architecture changes.

## 20. Definition of DCM ALIVE

```text
DCM_ALIVE = public RDF admitted
          AND lossless projection
          AND structural scan executed
          AND complete non-truncated reversible closure executed
          AND semantic DO frontier admitted
          AND explicit cut bound
          AND independent authority admitted
          AND real consequence executed
          AND independent postcondition verified
          AND closure-bound receipt persisted
          AND exact replay verified
```

Source code, importability, a workflow declaration or an earlier provider test is
insufficient.

## 21. Strategic experiment

The canonical experiment is:

```text
O -> O* -> graph -> closure -> cut -> BRCE -> E -> O' -> V -> R
R -> mine -> graph-route manufacture -> index -> re-admit -> reuse
```

Run 1 may use generalized cognition to discover causal machinery. Mature repetitions
should move cold -> warm -> hot by retrieving and re-admitting proven graph routes,
while authority and verification remain identical or stronger.

## 22. Ultimate requirement

GymAct succeeds when heterogeneous executable systems can participate in planning,
process semantics, self-play, benchmarking, authority, consequence verification,
receipts and replay without bespoke agent-tool decision semantics.

The target is not “maximum autonomy.” It is:

```text
maximum lawful verified consequence
with maximum preserved reversible possibility
and minimum repeated cognition
```

GymAct is the boundary where intelligence becomes causal machinery without becoming
ambient authority.
