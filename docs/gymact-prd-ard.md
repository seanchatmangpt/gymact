# GymAct — Product Requirements & Architecture Definition

**Version:** 26.8.7  
**Status:** Crown requirements / architectural constitution  
**Parent:** AutoFDE / AutoFDE Lab  
**Role:** Universal semantic effector and consequence-observation layer

## 0. Executive definition

GymAct is the universal executable-world abstraction for AutoFDE. It provides one semantic interface through which heterogeneous systems can be inspected, capability-discovered, semantically addressed, prepared for mutation, actuated through BRCE, independently observed, verified against declared postconditions, reconciled after uncertain outcomes, receipted, replayed, benchmarked, and process-mined.

GymAct does **not** pretend that Kubernetes, browsers, Git, databases, SaaS APIs, MCP servers, A2A peers, BPMN engines, robots, industrial controllers, simulations, and benchmark worlds share identical physics. It normalizes the calculus of consequential interaction while preserving provider-specific latency, consistency, atomicity, reversibility, idempotency, safety, identity, authority, and partial-failure behavior.

The canonical transition is:

```text
S_t -> candidate intent -> admission -> BRCE -> E -> independent O' -> V -> R
```

where `S_t` is the admitted pre-state, `E` is attempted external execution, `O'` is independently observed consequence, `V` is verification, and `R` is replayable receipt.

Primary optimization target:

```text
VCT = independently verified valuable state transitions
      -------------------------------------------------
      wall time * cost * human intervention
```

## 1. Product mission

GymAct SHALL make heterogeneous executable worlds behave like rigorously defined experimental environments without reducing them to mocks or hiding their unique failure modes.

The production path is:

```text
planner -> candidate intent -> GymAct semantic action -> BRCE
        -> provider -> external state -> observer -> verifier -> receipt
```

GymAct SHALL lower integration cost, causal latency, one-off model/tool glue, repeated API cognition, unsafe retry risk, and ambiguity about whether a command actually produced the intended consequence.

## 2. Product boundaries

GymAct SHALL NOT become:

- a planner: it receives candidate intents; it does not own global policy selection;
- an authorization authority: it declares authority requirements and consumes admitted grants;
- an agent framework: generalized reasoning, conversational sessions, and agent memory live elsewhere;
- a workflow-semantics replacement: POWL/BPMN/Temporal-class systems remain distinct;
- a proprietary ontology runtime: public semantic identities remain portable;
- a generic SDK wrapper: wrapping an API without effect, authority, observation, verification, and receipt semantics is insufficient;
- a mock-based crown: mocks can prove mechanics, never integration standing.

## 3. Foundational laws

### G-LAW-001 — Zero unreceipted actuation

Every production consequential operation SHALL traverse BRCE.

```text
DO => BRCE => receipt | typed refusal/uncertainty
```

No provider adapter may expose a production mutation path that bypasses this boundary.

### G-LAW-002 — Candidate is not authority

`request != candidate != admitted intent != execution grant != actuation`.

Planner output, model output, CLI input, MCP calls, A2A messages, workflow edges, and generated artifacts manufacture candidate intent only.

### G-LAW-003 — Acknowledgement is not effect

GymAct SHALL keep these states distinct:

```text
accepted != executed != world_changed != postcondition_observed != objective_verified
```

### G-LAW-004 — Independent observation

Whenever technically possible, consequence SHALL be established by an observation path independent from the mutating call. Provider self-report is evidence with lower confidence, not universal proof.

### G-LAW-005 — No blind retry

Possible actuation plus lost acknowledgement SHALL transition:

```text
UNCERTAIN -> RECONCILE -> OBSERVE -> DECIDE
```

not directly to retry unless declared idempotency makes retry lawful.

### G-LAW-006 — Preserve provider physics

GymAct normalizes contracts, not reality. Provider-specific transactionality, convergence, latency, rollback, safety, and consistency semantics remain explicit.

### G-LAW-007 — No mock crown

Only witnessed execution against a real compatible subject can establish `ALIVE` for that integration claim.

### G-LAW-008 — Refusal is positive evidence

A lawful typed refusal preserves more standing than an unverifiable success.

## 4. Standing and evidence

Canonical standing ladder:

```text
UNKNOWN < CANDIDATE < STRUCTURAL < PARTIAL_ALIVE < ALIVE < ADOPTED
```

Orthogonal states/reasons include `BLOCKED`, `BUILD_BROKEN`, `UNSUPPORTED`, `REQUIRES_CONFIGURATION`, `REFUSED`, `UNCERTAIN`, and `STALE`.

GymAct SHALL keep the following evidence predicates distinct:

- observed;
- admitted;
- executed;
- changed;
- verified;
- inferred;
- refused;
- blocked;
- unsupported.

`ALIVE` requires observed execution against the exact compatible subject and adequate verification for the claimed behavior. `ADOPTED` requires external consequential use and cannot be manufactured from internal fixtures.

## 5. Semantic action contract

Every consequential action SHALL declare:

- semantic identity;
- provider identity;
- capability identity;
- subject type;
- input/output contracts;
- preconditions;
- authority requirements;
- expected effects;
- verification strategy;
- idempotency class and key material;
- reconciliation strategy;
- rollback/compensation semantics;
- cost model;
- causal locality;
- standing/evidence references.

The contract SHALL be inspectable without granting execution authority.

## 6. Canonical domain model

GymAct SHALL explicitly represent at least:

`Provider`, `Capability`, `ActionDefinition`, `Subject`, `SubjectIdentity`, `Observation`, `DesiredEffect`, `Precondition`, `Postcondition`, `Intent`, `Admission`, `AuthorityRequirement`, `ExecutionGrant`, `ExecutionAttempt`, `Acknowledgement`, `ObservedEffect`, `Verification`, `Evidence`, `Receipt`, `Refusal`, `Uncertainty`, `Reconciliation`, `Rollback`, `CostObservation`, and `Standing`.

Important domain objects SHALL NOT be aliased merely for API convenience.

## 7. P0 requirements

### G-P0-001 Semantic action model

Machine-inspectable action definitions SHALL exist independently from invocation.

### G-P0-002 Provider SPI

The provider contract SHALL expose capability discovery, observation, preparation, actuation, reconciliation, rollback/compensation where supported, and health/standing. `actuate()` alone is not a provider contract.

### G-P0-003 SELECT / CONSTRUCT / DO separation

GymAct SHALL preserve:

```text
SELECT    chooses candidate behavior
CONSTRUCT manufactures an executable intent
DO        actuates through BRCE
```

### G-P0-004 BRCE-exclusive DO

Production mutation SHALL be unreachable without an admitted execution grant and a receipted result.

### G-P0-005 Observation contract

Every provider SHALL expose independent observation where the external system permits it. Observations SHOULD have content identity.

### G-P0-006 Verification contract

Actions SHALL declare verifiable postconditions. Strategies may include exact state, predicate, SHACL, query result, digest, resource existence/absence, revision comparison, event evidence, process conformance, temporal stabilization, or multi-oracle quorum.

### G-P0-007 Idempotency contract

Every consequential action SHALL declare one of:

`IDEMPOTENT`, `CONDITIONALLY_IDEMPOTENT`, `NON_IDEMPOTENT`, `UNKNOWN`.

Unknown idempotency triggers strict retry refusal.

### G-P0-008 Uncertain-outcome reconciliation

Possible execution without definitive acknowledgement SHALL be represented explicitly and reconciled before retry.

### G-P0-009 Typed refusal taxonomy

At minimum:

- `AUTHORITY_REFUSED`
- `IDENTITY_REFUSED`
- `CAPABILITY_REFUSED`
- `PRECONDITION_REFUSED`
- `STALE_OBSERVATION_REFUSED`
- `REVISION_MISMATCH_REFUSED`
- `POLICY_REFUSED`
- `UNSAFE_RETRY_REFUSED`
- `AMBIGUOUS_SUBJECT_REFUSED`
- `VERIFICATION_REFUSED`
- `UNSUPPORTED_OPERATION`
- `PROVIDER_CONFIGURATION_REQUIRED`

### G-P0-010 Receipt binding

Each consequential attempt SHALL record requesting/admitted identity, operation, exact subject, provider, policy/authority evidence, admitted pre-state, execution disposition, acknowledgement status, independently observed post-state, verification evidence, idempotency identity, and resulting standing.

### G-P0-011 Revision binding

Where a subject exposes revisions (Git SHA, ETag, resourceVersion, generation, file digest, database version), admitted operations SHALL support optimistic revision binding. Drift fails closed unless policy explicitly admits it.

### G-P0-012 Heterogeneous real providers

GymAct ecosystem `ALIVE` requires at least three materially different real provider families. Initial Crown target: Git/GitHub, filesystem/database, and a network/distributed provider such as Kubernetes/MCP/cloud/SaaS.

### G-P0-013 CLI

Canonical surface:

```text
gymact providers
gymact capabilities
gymact inspect
gymact prepare
gymact execute
gymact observe
gymact verify
gymact reconcile
gymact replay
gymact doctor
gymact benchmark
```

`gymact execute` SHALL traverse BRCE.

### G-P0-014 Python API

The canonical semantic model SHALL be usable without subprocess shelling.

### G-P0-015 REST/OpenAPI

REST SHALL be a projection of the same domain behavior.

### G-P0-016 MCP/FastMCP

MCP SHALL transport/construct candidate intent, never grant ambient execution authority.

### G-P0-017 Protocol equivalence

CLI, Python, REST, MCP, and other projections SHALL preserve canonical action identity and semantics. Transport adapters SHALL NOT independently implement business behavior.

### G-P0-018 Structured evidence

Canonical receipts/evidence SHALL be machine-readable. Logs alone do not establish standing.

### G-P0-019 Content identity

Important definitions, intents, observations, evidence, and receipts SHOULD carry BLAKE3 identity where interoperable.

### G-P0-020 OCEL-compatible event projection

Consequential execution SHALL be projectable to OCEL/process evidence.

## 8. P1 requirements

GymAct SHOULD provide:

- RDF/JSON-LD semantic projection using public vocabularies;
- SHACL admission for important graph boundaries;
- PDDL/PPDDL/RDDL candidate-action projections without authority transfer;
- POWL v2 effect leaves;
- BPMN integration through BRCE;
- A2A as an intent transport, not an authority plane;
- action/provider cost models;
- causal-locality metadata;
- empirical provider benchmarking and Pareto selection;
- semantic capability caching that never caches authority admission;
- branch-before-mutation staging where available;
- explicit `REVERSIBLE`, `COMPENSATABLE`, `IRREVERSIBLE`, and `UNKNOWN` reversal classes;
- bounded fault injection;
- self-play from contracts;
- differential verification through independent access paths.

## 9. P2 requirements

GymAct SHALL remain extensible to:

- robotics;
- safely bounded OT/industrial protocols;
- edge controllers;
- WASM provider/controller deployment;
- ggen manufacture from admitted semantic graphs;
- empirical provider selection from receipt history.

## 10. Architecture

```text
CALLERS
Planner | Agent | POWL | BPMN | CLI | MCP | A2A
   |
   v
SEMANTIC INTENT PLANE
identity | subject | desired effect | preconditions | evidence requirements
   |
   v
ADMISSION
schema | SHACL | revision | capability | identity | policy references
   |
   v
BRCE
principal | authority | policy | scope | execution grant | receipt context
   |
   v
PROVIDER RUNTIME
prepare -> actuate -> acknowledge
   |
   v
EXTERNAL SYSTEM
   |
   v
OBSERVATION PLANE
independent inspect | event | state query | sensor
   |
   v
VERIFICATION PLANE
predicate | SHACL | diff | query | quorum | temporal stabilization
   |
   v
RECEIPT PLANE
evidence DAG | hashes | standing | OCEL | replay | metrics
```

## 11. Provider SPI

Conceptual provider contract:

```python
class GymProvider:
    def metadata(self): ...
    def capabilities(self, subject=None): ...
    async def inspect(self, subject, request): ...
    async def prepare(self, intent): ...
    async def actuate(self, grant, preparation): ...
    async def observe(self, subject, request): ...
    async def reconcile(self, uncertain): ...
    async def rollback(self, execution): ...
    async def health(self): ...
```

Unsupported behavior SHALL return a typed `UNSUPPORTED` result instead of invented semantics.

## 12. Provider families

Target families include source control, filesystem/process, browser, database, Kubernetes, cloud, infrastructure-as-code, MCP, A2A, workflow engines, enterprise SaaS, simulations/benchmarks, robotics, and safely bounded industrial systems.

Simulation `ALIVE` establishes simulation standing only; it cannot confer real-world integration standing.

## 13. Authority architecture

Execution grants SHALL bind:

- requesting principal;
- delegated principal if any;
- action/capability;
- exact subject/scope;
- authority source/evidence;
- policy revision;
- admitted observation/revision;
- expiry;
- nonce/idempotency material;
- intended effect.

No layer may widen authority. Having human permission SHALL NOT imply autonomous admission; GymAct/BRCE policy may be stricter.

## 14. Observation confidence

GymAct SHOULD classify observation evidence, for example:

`SELF_REPORTED`, `SAME_PROVIDER_OBSERVED`, `INDEPENDENT_CHANNEL`, `MULTI_ORACLE`, `PHYSICAL_SENSOR`.

The recorded standing SHALL match what was actually proven.

## 15. Receipts and replay

Receipts SHOULD form an evidence DAG:

```text
Observation -> Admission -> Intent -> Authority -> Execution
            -> Acknowledgement -> Post-observation -> Verification -> Standing
```

Replay SHALL distinguish:

- `EVIDENCE_REPLAY`
- `VERIFIER_REPLAY`
- `SIMULATION_REPLAY`
- `LIVE_REEXECUTION`

Replay SHALL never silently mutate external state.

## 16. Protocol projection

One canonical semantic implementation SHALL feed downstream transports:

```text
canonical action -> CLI
                 -> Python
                 -> REST
                 -> MCP
                 -> A2A
                 -> BPMN/POWL
```

Protocol differential tests SHALL detect divergence.

## 17. Planner integration

GymAct capability descriptions SHALL expose planner-relevant preconditions, effects, costs, duration, uncertainty, reversibility, resources, authority requirements, locality, and verification latency. Planner output remains a candidate until admission.

## 18. Cognition compilation and ggen

Successful cold-path API/tool reasoning SHOULD be mined for compilable structure:

```text
novel cognition -> admitted semantic action -> deterministic manufacture
                -> generated transport/provider/verifier projections -> indexed reuse
```

The admitted public-semantic graph remains canonical. Generated projections are regenerable artifacts, not independent editing authorities.

## 19. Self-play and mutation testing

From every action/provider contract, AutoFDE Lab SHOULD generate valid, boundary, stale, unauthorized, ambiguous, unsupported, lost-ACK, partial-effect, wrong-effect, delayed-effect, irreversible, duplicate, and replay-mismatch scenarios.

Critical mutation tests MUST fail when an implementation:

1. bypasses BRCE;
2. treats transport success as verified consequence;
3. removes authority checks;
4. removes revision checks;
5. blindly retries an uncertain non-idempotent action;
6. crowns a mock as `ALIVE`;
7. maps `UNSUPPORTED` to success;
8. skips post-observation;
9. permits receipt tampering;
10. widens delegated authority;
11. ignores verifier failure;
12. aliases compensation to rollback.

## 20. GALL checkpoint ladder

- **CP0 BUILD** — package builds/imports; ceiling `STRUCTURAL`.
- **CP1 CONTRACT** — action/provider/refusal contracts mechanically validate; ceiling `STRUCTURAL`.
- **CP2 LOCAL EXECUTION** — real local subject, actuation, independent observation, verification, receipt; `PARTIAL_ALIVE`.
- **CP3 REMOTE EXECUTION** — at least one real networked provider.
- **CP4 AUTHORITY FAILURE** — invalid authority cannot actuate; mutation removal is caught.
- **CP5 REVISION FAILURE** — stale admitted revision produces typed refusal with no mutation.
- **CP6 UNCERTAIN EXECUTION** — lost acknowledgement enters reconciliation, never blind retry.
- **CP7 INDEPENDENT VERIFICATION** — execute and verify through materially separate paths where possible.
- **CP8 PROTOCOL EQUIVALENCE** — transport projections manufacture equivalent canonical intent.
- **CP9 MULTI-PROVIDER** — three materially distinct real provider families execute verified consequence.
- **CP10 SELF-PLAY** — bounded combinatorial scenarios execute with zero incorrect crowns for safety invariants.
- **CP11 DIFFERENTIAL ORACLE** — at least one provider verified by independent implementation/channel.
- **CP12 FAULT INJECTION** — timeout, stale state, duplicate, dependency failure, delayed observation, and lost ACK.
- **CP13 PROCESS EVIDENCE** — OCEL-compatible execution corpus supports process analysis.
- **CP14 REPLAY** — persisted receipt/evidence replay detects tampering/drift.
- **CP15 ECONOMIC BENCHMARK** — VCT, tokens, cost, latency, retries, interventions, reconciliation measured.
- **CP16 COGNITION COMPILE-OUT** — a formerly cognition-heavy task executes through manufactured indexed capability with lower repeated cognition and no weakened authority/verification.

## 21. Definition of ALIVE

```text
ALIVE(capability) = structural contract
                  AND real execution
                  AND observed effect
                  AND verified postcondition
                  AND replayable receipt
```

For consequential capability: `ALIVE(DO) => BRCE`.

Importability, a mock, HTTP 200, workflow configuration, MCP discovery, or provider self-report alone is insufficient.

## 22. Conformance suite

Every consequential provider SHALL inherit common tests for identity, revision, capability, authority, execution, idempotency, independent observation, verification, uncertainty/reconciliation, receipts, and replay.

## 23. Strategic Crown experiment

The canonical experiment is:

```text
O -> O* -> intent -> BRCE -> GymAct -> E -> O' -> V -> R
R -> mine -> manufacture -> index -> reuse
```

Run 1 may use generalized cognition to discover provider/capability/arguments/verifier/reconciliation semantics. The successful pattern is then compiled into an admitted action and deterministic projections. Run 2 SHOULD narrow to a warm-path candidate set. Mature repetitions SHOULD reach a hot path:

```text
admitted observation -> indexed capability -> deterministic intent -> BRCE
                     -> provider -> independent observation -> verification -> receipt
```

with `C_LLM = 0` where the problem class permits.

## 24. Anti-agent economic experiment

For representative recurring workloads, compare a frontier model/tool loop to the manufactured GymAct path over `N in {1, 10, 100, 1000, 10000}`. Measure verified success, false success, monetary cost, tokens, wall time, compute, human approval/intervention, retries, uncertainty, reconciliation latency, and replay success.

The desired result is an empirically observed crossover `N*` after which GymAct has lower marginal cost while preserving stronger verification and authority.

## 25. Falsifiers

The architecture is falsified if any of the following becomes canonical:

- planner/model output directly mutates external state;
- acknowledgement is accepted as verified consequence;
- mocks establish production `ALIVE`;
- unknown idempotency permits blind retry;
- transport adapters contain independent business logic;
- provider schemas become proprietary ontology lock-in;
- capability caching bypasses authority;
- replay silently re-executes consequential behavior;
- generated code becomes canonical rather than regenerable;
- provider diversity is flattened until important physics disappear;
- GymAct devolves into another generalized agent-tool framework.

## 26. Release gates

### v26.8.7 foundation

Required: semantic action model, provider SPI, typed standing/refusal, observation, verification, receipts, BRCE boundary, Python/CLI, and at least one real local provider. Target standing: `PARTIAL_ALIVE` unless stronger exact-head evidence exists.

### Crown candidate

Required: three heterogeneous real providers, transport equivalence, revision refusal, lost-ACK reconciliation, independent verification, replay/tamper detection, mutation tests, and OCEL process evidence.

### Manufacture phase

Required: ontology-defined actions, SHACL, ggen projections, POWL/planner projections, self-play generation, empirical provider benchmarking, and capability indexes.

### Crown

Required: witnessed `cold -> warm -> hot` compile-out with reduced repeated model cognition and identical-or-stronger authority, verification, receipt, and replay guarantees.

## 27. Ultimate requirement

GymAct succeeds when new executable systems no longer require bespoke agent-tool semantics. The long-term target is:

```text
ProviderDescription + PublicOntology + Capability + Authority + Verification
    -> lawful manufacture
    -> GymAct capability
```

which can participate in planning, workflow, process mining, self-play, benchmarking, BRCE, receipt, replay, and cognition compile-out without changing its causal meaning.

**GymAct is where admitted computational intent encounters consequential reality. Its job is to make that encounter lawful, measurable, falsifiable, independently verifiable, replayable, and progressively compilable out of repeated cognition.**
