# Consequence Boundaries in Bounded Executable Worlds: An Architecture for Verifiably-Actuated Benchmark Runtimes

**A technical thesis on the GymAct project**

---

## Abstract

GymAct is a reference Python runtime for a public-semantic execution profile over bounded
benchmark worlds — Kubernetes clusters, Terraform-managed infrastructure, cloud simulations,
codebases, and dozens of other "gyms." Its central claim, stated in the project's own governing
law, is that four distinct events routinely get collapsed into one in agent-benchmark tooling and
must not be:

```text
request accepted != world changed != objective verified != benchmark scored
```

This thesis describes the architecture GymAct builds to keep those four events separate and
independently checkable: a small kernel (`GymAct`) that gates every consequential operation
behind an externally-injected, fail-closed `AuthorityResolver`; renders every verification
verdict through an externally-injected `PostconditionVerifier` rather than trusting a provider's
self-report; and grounds every "this gym actually ran" claim in a real, schema-validated,
conformance-replayed OCEL 2.0 event log rather than a passing test suite. It further describes
the project's semantic discipline — building exclusively on public RDF/OWL vocabularies (PROV-O,
SOSA/SSN, ODRL, SHACL, EARL, and others) rather than a bespoke ontology — and presents, as a case
study, the Epistemic Process Kernel (EPK): a domain-general DSPy-based diagnostic agent built this
session on top of the kernel, evaluated honestly on both a live Kubernetes-cluster benchmark
(sregym) and a fast in-process world (`MemoryProvider`), with its unresolved gaps reported
alongside its working parts.

---

## 1. Introduction

Agent-benchmark tooling has a recurring failure mode: a tool call returns 200, an LLM narrates
success, and nothing downstream checks whether the described consequence actually happened in the
world, or whether "happened" was itself evaluated by the same actor that performed it. Four
different claims get treated as one:

1. **Request accepted** — the API/tool call was syntactically valid and the runtime agreed to
   attempt it.
2. **World changed** — a real actuation occurred against a real external system.
3. **Objective verified** — an *independent* check confirms the actuation produced the intended
   state.
4. **Benchmark scored** — that verified state satisfies whatever grading contract the benchmark
   defines.

GymAct's engineering law (`CLAUDE.md`) states this collapse explicitly as four things that must
never be conflated, and derives from it a small number of concrete, checkable rules: an
`authority_ref` is not permission; required authority is fail-closed unless an injected resolver
explicitly admits the exact operation; a transport must never grant authority by itself; provider
failures must not disappear as successful or unreceipted operations; and idempotency-key reuse
with a different intent is a refusal, not a replay.

This thesis is an account of how that law is actually enforced in code — not as aspiration, but
as a small number of concrete architectural decisions, each traceable to a specific defect that
motivated it. Section 4 covers the kernel; Section 5 the semantic discipline; Section 6 the
evidence methodology; Section 7 a real case study (the Epistemic Process Kernel) that exercises
all of the above against a live external system; Section 8 discusses what is proven and what
remains open.

---

## 2. Related Work and Positioning

GymAct sits adjacent to several existing lines of tooling rather than replacing any of them:

- **Episodic RL APIs** (Gymnasium, PettingZoo) establish the `reset`/`step`/`observe` shape that
  GymAct's `materialize`/`observe`/`act` operations echo, but GymAct adds an authority boundary
  and independent verification layer that a pure RL environment API has no reason to need — an RL
  environment's step function is trusted by construction; a benchmark harness executing real
  infrastructure changes cannot be.
- **MCP-based tool-calling agents** treat a tool's return value as ground truth. GymAct's
  `PostconditionVerifier` design is a direct rejection of this pattern: a tool call's own success
  report is collected as an audit signal, never as the verdict.
- **Benchmark harnesses with bespoke per-benchmark adapters** (SWE-bench-style single-purpose
  runners) are the shape GymAct's provider system generalizes: `sregym`, `kubernetes_reconciliation`,
  `terraform_docker_apply`, `terraform_plan`, `swegym`, `cube_counter`, and 15 other real providers
  under `src/gymact/gyms/` each implement one `Environment`/`EnvironmentProvider` pair conforming
  to the same eight-operation kernel surface, rather than each inventing its own success-reporting
  convention.
- **Naive LLM-agent-executes-tools designs** — the pattern GymAct's own consequence law exists to
  refuse. An agent proposing an action is manufacturing *intent*; only the kernel's authority
  boundary may turn intent into actuation, and only an independent verifier may certify effect.

GymAct's own distinguishing choice, developed further in Section 5, is refusing to define a
custom ontology for any of this: every domain concept above (actuation, observation, verification,
authority, evidence) is expressed as an instance of an existing public RDF vocabulary term rather
than a new GymAct-owned class.

---

## 3. The Gym Algebra

Before describing the kernel's implementation, it is worth stating the abstract model it
implements, drafted in the project's own constitution document
(`docs/2026-08-08-gymact-constitution.md`). A gym is modeled as an algebraic structure

```text
G = (S, O, C, A, Γ, T, V, R)
```

— a WorldState space, an Observation space, a Capability set, an Action space, an Authority
admission function (Γ), a Transition relation (T), a Verification function (V), and a Receipt/
replay record (R). Each component maps onto a specific public RDF vocabulary term: states and
transitions onto PROV-O's entity/activity model, capabilities onto SOSA's `Procedure`,
observations onto `sosa:Observation`, authority onto ODRL's `Policy`, verification onto EARL's
`Assertion`.

The document further identifies five conceptually distinct operations a benchmark process
performs — `OBSERVE`, `SELECT`, `CONSTRUCT`, `DO`, `VERIFY` — and states, deliberately, that
GymAct owns only three of them: `OBSERVE`, `DO`, `VERIFY`. `SELECT` (which capability or action to
choose) and `CONSTRUCT` (synthesizing a novel plan, payload, or provider) are left to callers
composing plans on top of GymAct's primitives — the harness, the contestant agent, or (as in
Section 7) a purpose-built epistemic kernel. The document names this explicitly as a design
choice rather than an omission: *"GymAct refusing to own SELECT/CONSTRUCT is not a missing
feature — it is the boundary that keeps the kernel smaller than benchmark-specific
integrations."*

A companion standing ladder — G0 Described, G1 Observable, G2 Consequential, G3 Verified, G4
Composable — gives graded language for how far a given gym has actually gotten: G1 means a real
`observe()` call returned a real `sosa:Observation` ("request accepted"); G2 means a real `DO`
capability actually changed the world ("world changed"); G3 means an independent verification
step confirmed it ("objective verified"). This ladder is the same distinction the consequence law
states in prose, given a name that lets a claim about any specific gym be pinned to a specific
rung rather than asserted in the aggregate.

---

## 4. Architecture: The `GymAct` Kernel

### 4.1 Surface

`GymAct` (`src/gymact/kernel.py`) exposes eight operations, matching `Operation`'s eight declared
values (`src/gymact/models.py:44`): `DISCOVER`, `MATERIALIZE`, `OBSERVE`, `ACT`, `VERIFY`,
`CHECKPOINT`, `RESTORE`, `TEARDOWN`. The class's own docstring states its intent directly:
*"Reference orchestrator with public semantics and bounded consequence law"* — and the module
docstring above it: *"Fortune-scale semantic kernel for bounded executable worlds. The kernel
preserves GymAct's evidence-backed eight-operation surface while hardening every external
consequence boundary with limits, fail-closed authority, BLAKE3 evidence, idempotency and
independent verification."*

Every construction defaults closed, not open (`kernel.py:83-110`):

```python
def __init__(
    self,
    *,
    validate_profile: bool = True,
    authority_resolver: AuthorityResolver | None = None,
    limits: RuntimeLimits | None = None,
    receipt_ledger: ReceiptLedger | None = None,
    verifier: PostconditionVerifier | None = None,
    capability_scope: CapabilityScope | None = None,
) -> None:
```

with `self._authority = authority_resolver or DenyAuthorityResolver()` and
`self._verifier = verifier or DictSubsetVerifier()`. A caller who constructs a bare `GymAct()`
gets a runtime that refuses every authority-gated operation and judges every verification
independently by default — the permissive path requires deliberately supplying a resolver, not
forgetting to lock one down.

### 4.2 The consequence gate inside `act()`

`act()` (`kernel.py:535`) is the single path by which any real-world effect occurs, and its
docstring — *"Attempt one semantic actuation with authority, limits and replay gates"* —
enumerates exactly what stands between a caller's `ActuationIntent` and a provider's `actuate()`
call:

1. **Idempotency-key replay check** — a duplicate key against a different intent is refused, not
   silently replayed; this directly implements the consequence law's fifth rule.
2. **Input-size bound** (`_ensure_input`).
3. **Capability lookup** — an unknown capability IRI is refused as `UNSUPPORTED`.
4. **Consequence check** — if `capability.consequence is not Consequence.DO`, the call is refused
   with `READ_CAPABILITY_IS_NOT_ACTUATION`. `Consequence` (`models.py:37`) is a two-value
   `StrEnum`, `READ` or `DO`; a capability declared `READ` mechanically cannot be actuated through
   this path regardless of what it semantically does. Section 7.4 reports a real defect this gate
   surfaced: eleven sregym capabilities that were semantically read-only (Jaeger/Loki/Prometheus
   queries, cluster status reads) were declared `Consequence.READ` and were therefore silently
   refused by every attempt to invoke them through `act()`, because their only real invocation
   path — proxying through an MCP tool call — is mechanically a `DO`, whatever their semantics.
5. **`CapabilityScope.permits()`** — a second, independent scoping check
   (`CAPABILITY_NOT_IN_SCOPE`).
6. **`_authority_decision()`** — described below.
7. **Provider `actuate()` call**, wrapped in a bounded timeout and exception handler so a
   provider failure cannot silently present as a successful, unreceipted operation.

### 4.3 The authority boundary, and a closed historical gap

`_authority_decision()` (`kernel.py:200-225`) is where an `AuthorityResolver` is actually
consulted:

```python
async def _authority_decision(
    self, *, required: bool, episode_id: str, subject_ref: str,
    operation: Operation, capability_ref: str, payload: dict[str, Any],
    authority_ref: str | None,
) -> AuthorityDecision:
    if not required:
        return AuthorityDecision(admitted=True, reason="AUTHORITY_NOT_REQUIRED")
    request = AuthorityRequest(...)
    return await self._bounded(self.limits.authority_timeout_s, "AUTHORITY_TIMEOUT",
        lambda: self._authority.authorize(request))
```

The `required` parameter is the load-bearing detail: when a caller's `required` flag is `False`,
the resolver is never consulted at all. This exact shape produced a real, closed defect,
documented in `.claude/rules/actuation-authority.md`: eight providers with genuine external side
effects — real `kubectl apply`/`delete`, real `terraform apply`/`destroy`, among others — defaulted
their own `config.get("requires_authority", False)` to `False`, meaning their consequential
operations bypassed the authority boundary entirely by default rather than merely being
permissively authorized. The fix, narrowly scoped and confirmed by re-running the full affected
test suites twice, flipped each provider's default to `True`; every test that had relied on the
old unauthorized-by-default path was individually updated to construct an explicit
`AllowListAuthorityResolver` and pass an explicit `authority_ref`. The same rule file documents
what was deliberately *not* touched — `MemoryProvider`'s equivalent default, and two other
providers whose flip broke roughly 27 unrelated tests — naming both as still-open, unaudited
items rather than silently expanding the fix's scope.

### 4.4 Independent verification, and the self-certification bug it replaced

`verify()` (`kernel.py:799`) is the second load-bearing boundary. Its docstring states the
history precisely:

> "The provider's own `Environment.verify(expected)` is still called and its report is still
> returned as `observed`/for divergence detection, but its `passed` boolean is never trusted as
> the result: `self._verifier` (an injected `PostconditionVerifier`, defaulting to
> `DictSubsetVerifier`, never the provider itself) independently judges `expected` against a
> fresh, kernel-triggered `observe()` read... If the provider's own self-report disagrees with the
> independent judgment, that divergence is real, positive evidence of a dishonest or buggy
> provider and is appended to the Receipt's `reason`, never silently discarded."

The module this implements, `src/gymact/verification.py`, states the bug it replaces even more
directly in its own module docstring: before this module existed, `GymAct.verify()` called
`state.environment.verify(expected)` and trusted whatever `(passed, observed)` tuple the provider
itself computed — the provider both produced the observation and rendered the verdict. The
docstring names two confirmed, concrete instances where this mattered: `gymact.gyms
.vendor_benchmarks` and `gymact.gyms.sregym`'s own `verify()` implementations both computed
`passed` from their own observation with no external check, meaning either could in principle
report `passed=True` unconditionally and nothing downstream would catch it.

`PostconditionVerifier` is a `runtime_checkable` `Protocol` with a single method,
`judge(expected, observed) -> tuple[bool, str]`, and its docstring is explicit about the design
principle: *"Never implemented by a provider/Environment — injected into `GymAct`, exactly like
`AuthorityResolver`."* The default implementation, `DictSubsetVerifier`, reproduces
`gymact.local_providers`'s own recursive-subset matching semantics exactly — `expected` is judged
as a required recursive subset of `observed`, computed over the kernel's own independent
`observe()` call, never over anything the provider asserts about itself.

Section 7.4 reports a second real defect this exact boundary surfaced downstream, in code merged
this session: a provider (`OpaqueProcedureEnvironment`) whose own `verify()` correctly computed a
`goal_reached` predicate, but whose `observe()` never exposed that predicate as an observable
fact — meaning the externally-injected `DictSubsetVerifier`, which only ever sees `observe()`'s
output, could never confirm the goal was reached regardless of the real underlying state. This is
presented not as a flaw in the verification design but as exactly the kind of gap the design is
meant to surface: a provider whose self-report and independently-observable state disagree is a
real, checkable finding, not a silent pass.

### 4.5 Teardown scope

A related, narrower law, also documented in `actuation-authority.md`, governs what a provider's
`teardown()`/`restore()` is permitted to target: only resources it can name-trace back to its own
`materialize()` call — ids or names it generated and tracked at creation time — never a
cluster-wide or account-wide "reconcile to baseline" sweep that deletes anything not in an
expected set. `kubernetes_reconciliation.py`'s `teardown()` is cited as the repo's own positive
example: it issues a name-scoped `kubectl delete pod <self._pod_name>`, where `self._pod_name` is
a UUID this provider's own `materialize()` generated and tracked on the instance, so teardown can
mechanically only ever target the one pod it made. The rule names a real negative example that
motivated writing this down explicitly: SREGym's own (upstream, non-GymAct) conductor cleanup
routine deletes cluster-wide Kubernetes `ClusterRoleBinding`s via exactly the forbidden
sweep-to-baseline pattern — real, but vendored code outside GymAct's own providers, cited here as
a documented cautionary case rather than a defect in this codebase.

---

## 5. Semantic Discipline: Public Vocabularies, No Custom TBox

GymAct's second architectural pillar is a strict refusal to define its own domain ontology.
`.claude/rules/ontology.md` states the rule directly: GymAct is a `prof:Profile` — an
application profile that constrains and composes existing public ontologies, never a competing
class hierarchy. `urn:gymact:*` local IRIs are reserved for instance data, SKOS concepts, SHACL
shapes, and profile resources only.

The rule specifies a stack of thirteen public vocabularies, each assigned a specific concern:
PROF for profile identity, PROV-O for provenance, P-PLAN for prospective plans, SOSA/SSN for
observation/actuation, WoT TD/TM for the executable world model, ODRL for authority, SHACL for
executable constraints, EARL for verification results, DQV for quality metrics, QUDT for
quantitative values, DCAT for datasets, SKOS for taxonomies, OWL-Time for temporal structure, and
DCTERMS for metadata — plus RO-Crate for evidence packaging and DOAP/SPDX/Schema.org/GeoSPARQL/
DPV/FOAF for software, geography, privacy, and identity concerns respectively.

A concrete replacement table in the rule file names specific classes an earlier design considered
and rejected in favor of existing public terms — `GymDefinition` → `wot-tm:ThingModel`,
`EnvironmentInstance` → `wot-td:Thing`, `Action` (consequential) → `sosa:Actuation`/`prov:Activity`,
`Verifier`/`VerificationResult` → EARL's `earl:Assertion`/`earl:outcome`, `AuthorityEnvelope` →
`odrl:Policy`, and so on — a direct, checkable record of the ontology-mapping decisions this
codebase actually made, not an abstract policy.

The rule also requires that any rejection of a candidate public vocabulary be documented in the
consuming file's own header, not silently omitted — a discipline the project states is already
followed in `ggen/multicloud-gym-pack/ontology.ttl`'s header comments and is made an explicit,
repo-wide rule from that precedent.

The stated payoff (`ggen-boundary.md`, `ontology.md`) is that reusing well-understood public terms
means the Rust/WASM manufacturing layer (`ggen`) can project directly from an admitted RDF graph
into Rust types, WIT interfaces, and WASM components as *free consequences* of vocabulary
semantics already shared with existing tooling, rather than as bespoke template logic re-deriving
meaning from a private ontology every new integration would otherwise have to learn from scratch.

---

## 6. Evidence and Standing Methodology

### 6.1 The problem with trusting a passing test suite

`.claude/rules/ocel-standing.md` states a distinction central to how this project reports on
itself: whether a gym "works" is a claim about a real, independently observed and verified
consequence — never a claim about whether its own unit tests pass. A provider's pytest suite can
correctly and legitimately pass while proving only that its Python API behaves correctly given
its inputs; that says nothing about whether a real end-to-end episode was actually executed and
independently verified. The rule states the reason this distinction matters in the codebase's own
vocabulary: a green pytest run is evidence of "request accepted," never of "objective verified" —
reporting the former as the latter is precisely the collapse the consequence law forbids.

### 6.2 OCEL 2.0 as ground truth

The only artifact permitted to back a "this gym is actuated" claim is a real
`reports/ocel/<subject>/episode.ocel.json` log, derived the same way every time: (1) real
`jsonschema` validation against the real, vendored official OCEL 2.0 JSON Schema; (2) real replay
of the extracted operation sequence, in real recorded event order, via a `ConformanceChecker`;
(3) real `solved=True` evidence read directly off a real `act` event's own attributes, never off a
summarizing script's own packaged verdict.

`src/gymact/ocel.py`'s module docstring frames the design intent directly: *"This is the fix for
'claims must be checkable, not narrated': a standing claim like 'GymAct actuated subject X' should
be re-derivable by an independent party from a real, schema-conformant, content-addressed log —
not trusted from prose in a lock file."* `receipts_to_ocel()` builds an OCEL 2.0 log directly from
a list of real `Receipt`s — object types `episode`/`environment`/`capability`, event types one per
distinct `Operation` value actually observed — with the docstring stating plainly that "nothing
here is synthesized or inferred." `digest_ocel_log()`/`write_ocel_log()` compute a sha256 digest
over the exact canonical-JSON bytes written to disk, a detail the module's own docstring notes was
"caught and fixed during this session precisely because it wasn't" previously true — evidence the
project treats its own evidence-generation code as subject to the same scrutiny as everything
else.

### 6.3 Conformance replay

`src/gymact/process.py` declares the kernel's lifecycle as a real, hand-checkable transition
table over `Operation`'s eight values — explicitly narrower, per its own docstring, than "the 12
[operations] an earlier ontology-design pass described (no configure/reset/start/score here)," a
direct record of a design simplification the project made and kept. `LIFECYCLE` states legal
adjacencies (`DISCOVER → {MATERIALIZE}` as the only legal start-adjacent edge;
`MATERIALIZE`/`OBSERVE`/`ACT`/`VERIFY`/`CHECKPOINT`/`RESTORE` freely interleaving; `TEARDOWN`
terminal). `ConformanceChecker.check()` replays a real sequence of `Receipt.operation` values
against this table and returns a `ConformanceResult` with `conformant: bool` and a list of named
`Deviation`s (index, from-operation, to-operation, reason) — the class's own docstring: "Real
replay outcome: pass/fail with named evidence, not a fuzzy score."

Together, schema validation, conformance replay, and direct `solved=True` grounding implement the
three-part methodology `ocel-standing.md` names as the only legitimate basis for an "actuated"
claim — and this thesis's own Section 7 case study is reported against that same standard rather
than a summarized pytest result.

---

## 7. Case Study: The Epistemic Process Kernel (EPK)

### 7.1 Motivation and design boundary

The Epistemic Process Kernel is a domain-general diagnostic agent built this session directly on
top of the GymAct kernel described above, using a DSPy cognitive-operator library
(`src/gymact/epistemic_dspy.py`) as its typed reasoning substrate. Its own module docstring states
a design boundary as explicit as the gym algebra's SELECT/CONSTRUCT boundary in Section 3: *"DSPy
implements typed cognitive morphisms. It does NOT own: the process loop, tool execution, phase
transitions, canonical Fact IDs, epistemic state admission, action authority, actuation,
verification standing."* The host-Python sequencing loop
(`src/gymact/epistemic_process_kernel.py`) is what chooses which typed operator runs next; DSPy's
role is confined to individual, typed reasoning steps.

### 7.2 Substrate and operators

`epistemic_dspy.py` defines seventeen Pydantic substrate types spanning the full diagnostic
pipeline — `Fact`, `Constraint`, `Goal`, `Capability`, `ScenarioFrame`, `CandidateClaim`,
`HypothesisProposal`, `AdmittedHypothesis`, `EvidenceLinkProposal`, `EpistemicObligation`,
`EvidenceMapping`, `ReadCandidate`, `DiagnosisCandidate`, `PlanStep`, `CandidatePlan`,
`VerificationAssessment`, `ReceiptExplanation` — and nine corresponding DSPy `Signature`/`Module`
pairs: `ScenarioFramer`, `CandidateClaimExtractor`, `Hypothesizer`, `EvidenceLinker`,
`Discriminator`, `Diagnoser`, `PlanConstructor`, `VerificationInterpreter`, `ReceiptExplainer`.
None of these hard-codes a fixed fault taxonomy, a fixed tool list, or a `record_fact`/`finish`
tool of the kind a `dspy.ReAct` controller would typically expose — each operator is a narrow,
typed transformation over the substrate types, composed by the host loop rather than by the
model's own tool-selection behavior.

### 7.3 The sequencing loop

`run_episode()` implements the actual control flow:

1. **Hypothesize** — `Hypothesizer` proposes an initial `AdmittedHypothesis` portfolio, every
   member starting in state `UNKNOWN`.
2. **Per-round evidence linking** — `EvidenceLinker` maps current facts against current
   hypotheses; links are admitted only if they reference a real, already-grounded `fact_id`
   (`_admit_links`); each hypothesis's state is recomputed from its grounded links
   (`SUPPORTED`/`REFUTED`/`UNKNOWN`).
3. **Closure decision** — `next_kernel_action(supported_count, unknown_count)` is a small, pure
   function deciding among three branches: `"closure"` (exactly one supported hypothesis, zero
   unknown — the episode is ready to diagnose), `"rehypothesize"` (zero supported, zero unknown —
   every prior hypothesis was refuted, so a fresh portfolio is needed), or `"discriminate"`
   (otherwise — more evidence is needed to separate remaining candidates). This function was
   extracted and covered by four dedicated regression tests
   (`tests/test_epistemic_process_kernel_chicago.py`) specifically because an earlier, informal
   version of this same closure logic (`if not unresolved or len(supported) == 1: break`)
   incorrectly treated "four hypotheses simultaneously supported, zero unknown" as a terminal
   state — a real bug caught by exercising the loop against a live cluster, not by inspection.
4. **Discriminate** — when more evidence is needed, `Discriminator` proposes `ReadCandidate`s
   against the caller-supplied `read_capabilities`; each real candidate is executed through the
   GymAct kernel described in Section 4 (`_execute_capability`, a real `gym.act()`/`gym.observe()`
   call); resulting observations are passed to `CandidateClaimExtractor`, and any claim whose
   `source_observation_ids` do not correspond to a real observation from this round is refused
   with `REFUSED:UNGROUNDED_CLAIM` rather than silently admitted as a fact.
5. **Diagnose** — once closure is reached, `Diagnoser` commits a `DiagnosisCandidate`; the kernel
   independently checks that the diagnosis's own `supported_hypothesis_ids` matches the admitted
   state exactly, refusing with `DIAGNOSIS_DIVERGES_FROM_ADMITTED_STATE` if a downstream operator
   asserts something the upstream evidence-linking stage did not itself establish.
6. **Plan and verify** — `PlanConstructor` proposes a `CandidatePlan` restricted to the
   caller-supplied `do_capabilities`; plan steps are executed through the same kernel actuation
   path; `VerificationInterpreter` and `ReceiptExplainer` close the loop.

### 7.4 A generalization defect, found and fixed

An earlier version of `run_episode()` derived which capabilities were safe to expose to
Discriminate by internal heuristic — `consequence.value == "READ"` plus a naming check excluding
anything containing `"submit"`. This worked for sregym by coincidence, but the kernel's own
docstring (lines 244–262 of `epistemic_process_kernel.py`) names the concrete case where it would
have failed: `MemoryProvider`'s only real capabilities (`set`, `delete`, `increment`) are all
genuinely mutating `DO` operations with no safe read-only investigatory capability at all; the old
heuristic would have wrongly exposed one of them to Discriminate as if it were a harmless read.
The fix made `read_capability_bindings`/`do_capability_bindings` explicit, caller-supplied sets
rather than internally inferred — a design that trades a small amount of caller boilerplate for
the correctness property that a new provider's capability semantics are never guessed.

A second, independent defect was found by the same mechanism described in Section 4.2: eleven
sregym capabilities (`observe_cluster_state`, `get_benchmark_status`, and nine newly-added
Jaeger/Loki/Prometheus query capabilities) were declared `Consequence.READ`, matching their real
semantics, but the kernel's `act()` gate mechanically refuses any `Consequence.READ` capability
with `READ_CAPABILITY_IS_NOT_ACTUATION` — and these tool-shaped MCP capabilities have no other
invocation path. This was found only by adding real result-printing to a live-cluster run and
reading the actual refused outcomes, not by code inspection; the fix reclassified all eleven to
`Consequence.DO`, since their only mechanically real invocation path is through `act()`, whatever
their semantic content.

### 7.5 Real results, reported honestly

**Live sregym Kubernetes diagnosis** (`misconfig_app_hotel_res` scenario, run against a real
cluster via `scripts/run_epk_sregym_diagnosis.py`): across approximately seven live runs this
session, the episode never reached `admitted=True`. Increasing the round budget from 3 to 6 did
not change the outcome and was not pursued further given the flat result. Two concrete,
unaddressed gaps were named directly rather than papered over: repeated `kubectl get pod -l app=X`
queries return empty because the real, kompose-generated application under test uses
`io.kompose.service=X` labels rather than `app=X`; and a real jsonpath syntax error
(`invalid array index sidecar.istio.io/inject`) recurred across multiple Discriminate rounds. A
proposed fix for the first gap — deriving a pod-selector fact from each deployment's real,
observed labels — was implemented, then explicitly rejected during review as still constituting
sregym-specific hardcoding in the sregym-specific runner script, and was fully reverted. This
episode's honest standing, in the project's own vocabulary, is `REFUSED` at the
`NO_SUPPORTED_HYPOTHESIS`/`MULTIPLE_SUPPORTED_HYPOTHESES` boundary — not a failure to conceal, but
a real, checkable trace of what was tried and what remains open.

**In-process `MemoryProvider` portability proof** (`scripts/run_epk_memory_episode.py`): the exact
same kernel code, `run_episode()`/`explain_episode()`, run against a different, unrelated,
in-process world with a deliberately empty `read_capability_bindings` set (proving the kernel does
not assume every provider has a safe read path). Three real hypotheses were generated for this
completely different domain; the episode correctly reached `REFUSED:NO_SUPPORTED_HYPOTHESIS`
rather than fabricating a diagnosis; the real final `gym.observe()` state was confirmed unchanged;
teardown completed cleanly. This run is the concrete evidence for the claim that the kernel
generalizes across providers rather than being sregym-specific machinery with generic-looking
types.

---

## 8. Discussion

### 8.1 What generalizes

The EPK's control-flow (`next_kernel_action`, evidence-grounding, ungrounded-claim refusal,
diagnosis-divergence checking) is proven, by construction and by the `MemoryProvider` run, to be
provider-agnostic: nothing in `epistemic_process_kernel.py` references Kubernetes, sregym, or any
domain concept. The capability-binding fix in Section 7.4 is itself evidence that an earlier,
more convenient design *was* domain-specific in a way that was not obvious until tested against a
second, unrelated provider.

### 8.2 What remains open

The sregym scenario's non-closure is a real, unresolved gap, not a rounding error: a
real-cluster diagnostic loop with working mechanics (hypothesize, discriminate, evidence-link,
rehypothesize all genuinely execute) still failed to converge on this particular multi-fault
scenario across every attempt made this session. A generic, provider-agnostic repeated-tool-failure
feedback mechanism — detecting a real tool-level error in any executed capability's outcome and
feeding it back as a constraint for the next round, scoped entirely inside the generic kernel
rather than any provider-specific script — was scoped in discussion but not implemented before
this thesis was requested; it remains the most concrete, named next step.

### 8.3 A recurring correction pattern as methodology

Across this session, the single most repeated class of correction from review was catching
domain-specific hardcoding presented as general logic: an image-only deterministic outlier
predicate, a port-mismatch predicate, container-exit-code parsing baked into fact derivation, a
persona docstring's scenario-specific caution, and — most recently — a pod-selector fact
derivation embedded in the sregym-specific runner rather than the generic kernel. Each was caught,
reverted, and in several cases replaced by a more general mechanism (e.g., threading raw evidence
dicts as typed input fields rather than parsing them into hand-picked predicates, mirroring how
`dspy.ReAct`'s own trajectory-analysis pattern stays domain-agnostic). This repeated correction
loop is itself a methodological data point: building a genuinely domain-general diagnostic kernel
requires active, repeated resistance to the natural pull toward encoding just-this-one-benchmark's
structure into what is meant to be shared machinery — a pull that recurs even after being
corrected once, and that no single fix eliminates permanently.

### 8.4 The billing-block finding as a case study in the consequence law applied to CI

A smaller but structurally relevant finding from this session: four pull requests were merged
with all CI checks reporting "failure." Investigation of the real, raw CI logs — not the
paraphrased check names — found that every failed job across all four PRs carried an identical
GitHub Actions annotation: the jobs were never started at all, due to an account-level billing
block, not a code defect. This is a direct instance of the same distinction Section 6.1 draws for
pytest: a red CI check is not automatically evidence of "code does not work" any more than a green
one is automatically evidence that it does — both require reading what actually happened, not
trusting the status badge. The two real code defects the merge did surface (Section 4.4's
`goal_reached` observability gap, and an unrelated pre-existing regression that had silently
overwritten a module's algebraic content) were found only by then running real, local,
non-mocked tests — the same "trust the log, not the badge" discipline applied one layer down.

---

## 9. Conclusion

GymAct's central architectural claim — that request acceptance, world change, verified effect,
and benchmark score are four distinct, independently checkable events — is enforced, not merely
stated, through three concrete mechanisms: a fail-closed authority boundary that a caller must
deliberately open rather than accidentally leave shut; a verification boundary that never trusts
a provider's own report of its own success; and an evidence methodology that grounds "this ran"
claims in schema-validated, conformance-replayed event logs rather than test-suite color. The
project's semantic discipline — building exclusively on existing public RDF vocabularies rather
than a private ontology — is a complementary choice in the same direction: meaning that is legible
to tooling outside this codebase, rather than meaning privately invented and privately understood.

The Epistemic Process Kernel case study demonstrates these mechanisms exercised together against
a real external system, and reports its own limits in the same vocabulary it uses for everything
else it evaluates: `ALIVE` where a run genuinely closed, `REFUSED` where it honestly did not, and
named, specific, unresolved gaps rather than an aggregated success rate. That discipline —
applied to the project's own unfinished work as rigorously as to the systems it benchmarks — is,
by the project's own standard, the actual deliverable.

---

## References

**Public vocabularies composed by this project** (per `.claude/rules/ontology.md`):
PROF (W3C Profiles Vocabulary), PROV-O (W3C Provenance Ontology), P-PLAN, SOSA/SSN
(Sensor, Observation, Sample, and Actuator ontology), WoT Thing Description / Thing Model (W3C
Web of Things), ODRL (Open Digital Rights Language), SHACL (Shapes Constraint Language), EARL
(Evaluation and Report Language), DQV (Data Quality Vocabulary), QUDT (Quantities, Units,
Dimensions and Types), DCAT (Data Catalog Vocabulary), SKOS (Simple Knowledge Organization
System), OWL-Time, DCTERMS (Dublin Core Terms), RO-Crate (Research Object Crate), DOAP, SPDX,
Schema.org, GeoSPARQL, DPV (Data Privacy Vocabulary), FOAF.

**Software dependencies** (per `.claude/rules/python-native.md`): Pydantic v2, FastAPI, FastMCP,
Typer, FastStream, rdflib, pySHACL, httpx, anyio, tenacity, Gymnasium, PettingZoo, SpiffWorkflow,
DSPy.

**Primary sources within this codebase**: `src/gymact/kernel.py`, `src/gymact/models.py`,
`src/gymact/verification.py`, `src/gymact/ocel.py`, `src/gymact/process.py`,
`src/gymact/epistemic_dspy.py`, `src/gymact/epistemic_process_kernel.py`,
`docs/2026-08-08-gymact-constitution.md`, `.claude/rules/ontology.md`,
`.claude/rules/actuation-authority.md`, `.claude/rules/ocel-standing.md`,
`.claude/rules/explore-exploit.md`, `.claude/rules/ggen-boundary.md`,
`.claude/rules/python-native.md`, `CLAUDE.md`.
