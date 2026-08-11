"""The real Epistemic Process Kernel (EPK): the host-Python sequencing loop
`gymact.epistemic_dspy`'s own module docstring describes but deliberately
does not itself contain. This module owns:

- the process loop (Hypothesize -> EvidenceLink -> Discriminate -> Diagnose
  -> Construct -> BRCE -> Verify -> Explain),
- real Fact-ID minting (never DSPy output),
- deterministic epistemic-state computation (SUPPORTED/REFUTED/UNKNOWN is
  computed here, from grounded evidence links -- never emitted by an LM),
- real capability execution via `GymAct.act()` (no new authority path),
- diagnosis and plan admission gates.

`gymact.epistemic_dspy`'s cognitive operators propose; this module disposes.
Deliberately generic over any GymAct provider's capability surface -- no
sregym-specific literal appears here. A provider-specific runner script
(e.g. `scripts/run_epk_sregym_diagnosis.py`) supplies the real `Goal`,
`Constraint`s, capability discovery, and any provider-specific seed facts,
then calls `run_episode()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gymact.epistemic_dspy import (
    AdmittedHypothesis,
    CandidateClaimExtractor,
    CandidatePlan,
    Constraint,
    Diagnoser,
    DiagnosisCandidate,
    Discriminator,
    EvidenceLinker,
    Fact,
    Goal,
    Hypothesizer,
    PlanConstructor,
    ReadCandidate,
    ReceiptExplanation,
    VerificationAssessment,
)
from gymact.epistemic_dspy import Capability as EpistemicCapability
from gymact.kernel import GymAct
from gymact.models import ActuationIntent
from gymact.models import Capability as GymActCapability

# NOTE: `VerificationInterpreter`/`ReceiptExplainer` are deliberately not
# wired into `run_episode()` in this v1 -- `gym.verify()` is already
# kernel-owned and independent (see `gymact.kernel.GymAct.verify`); a
# provider-specific runner script may call `VerificationInterpreter`/
# `ReceiptExplainer` itself over the real `VerificationResult` for
# human-readable framing, without this module needing to own that step.
#
# `ReceiptExplainer` itself also can't cover a REFUSED episode --
# `ExplainReceipt`'s own InputFields (`diagnosis`, `selected_plan`,
# `execution_fact_ids`, `verification`) all require an admitted diagnosis
# that doesn't exist when `run_episode()` refuses. `explain_episode()`
# below is the real, separate answer to that gap: an honest, senior-SRE-
# style mentoring pass over whatever real evidence WAS gathered, whether
# or not the episode reached admission -- never fabricates a root cause
# the kernel itself did not admit.


@dataclass
class KernelStep:
    """One real, ordered trace entry -- mirrors `dspy_sregym_agent.
    SregymAgentStep`'s role: a human-auditable record of what actually
    happened, independent of any LM's own narration of it."""

    kind: str
    payload: dict[str, Any]
    result: Any


@dataclass
class EpistemicKernelResult:
    admitted: bool
    admission_reason: str
    diagnosis: DiagnosisCandidate | None
    selected_plan: CandidatePlan | None
    facts: list[Fact]
    hypotheses: list[AdmittedHypothesis]
    diagnosis_submitted: bool = False
    mitigation_submitted: bool = False
    verification: VerificationAssessment | None = None
    explanation: ReceiptExplanation | None = None
    rounds_used: int = 0
    steps: list[KernelStep] = field(default_factory=list)


def _adapt_capability(cap: GymActCapability) -> EpistemicCapability:
    """Real gymact `Capability` (`iri`/`title`/`consequence`/`binding`) ->
    `epistemic_dspy.Capability`. `id=iri` so a capability_id the model
    references can always be resolved back to a real gymact capability by
    exact string match -- no fuzzy binding-name matching."""
    return EpistemicCapability(
        id=cap.iri,
        consequence=cap.consequence.value,
        description=cap.title,
        parameter_schema={},
    )


def _find_gymact_capability(
    capabilities: tuple[GymActCapability, ...], capability_id: str
) -> GymActCapability | None:
    for cap in capabilities:
        if cap.iri == capability_id:
            return cap
    return None


async def _execute_capability(
    gym: GymAct,
    episode_id: str,
    authority_ref: str,
    capability: GymActCapability,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Real, single actuation path -- every DO/READ capability call in this
    module goes through here, matching every other real actuation in this
    repo (`dspy_sregym_agent.py`'s own `_run_kubectl_raw`-shaped closures):
    real `gym.act()`, real `ActuationIntent`, no new authority path. The
    real effect (not the separate post-actuation `observation`) is what
    carries real evidence -- see `dspy_sregym_agent.py`'s own documented
    gotcha for why these two must never be conflated."""
    result = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability.iri,
            payload=payload,
            authority_ref=authority_ref,
        )
    )
    return {
        "accepted": result.accepted,
        "standing": result.standing.value,
        "reason": result.receipt.reason if hasattr(result.receipt, "reason") else None,
        "effect": result.effect or {},
    }


def _admit_links(
    links: list[Any], fact_ids: set[str]
) -> tuple[list[Any], list[str]]:
    """Real referential-integrity check over `EvidenceLinkProposal`s --
    the same discipline `epistemic_kernel.admit_diagnosis` applied to
    `evidence_ids`, relocated to where this design puts state computation.
    A link citing a fact_id not in the real fact store is refused, not
    silently kept.

    This is the same structural requirement van der Aalst's "No AI Without
    PI!" (arXiv:2508.00116) names for process-intelligence-grounded AI: an
    answer with no real, linked grounding is inadmissible, not merely
    discouraged. The paper's own words, describing the failure mode this
    function's refusal prevents: "just sending textually encoded process
    variants or DFGs to the GenAI is enough to generate answers, but these
    are not very reliable." See `tests/test_epistemic_process_kernel_
    chicago.py::TestAdmitLinks` for real, direct coverage of this refusal."""
    admitted = []
    refused_reasons = []
    for link in links:
        if link.fact_id in fact_ids:
            admitted.append(link)
        else:
            refused_reasons.append(
                f"REFUSED:UNGROUNDED_LINK -- hypothesis_id={link.hypothesis_id!r} cites "
                f"fact_id={link.fact_id!r}, not present in the real fact store"
            )
    return admitted, refused_reasons


def _admit_claims(
    claims: list[Any], real_obs_ids: set[str]
) -> tuple[list[Any], list[str]]:
    """Real referential-integrity check over `CandidateClaim`s -- the same
    discipline `_admit_links` applies to `fact_id`, applied here to
    `source_observation_ids`. A claim citing an observation id no real
    Discriminate call actually produced is refused, not admitted on the
    LM's own say-so.

    This is the same structural requirement van der Aalst's "No AI Without
    PI!" (arXiv:2508.00116) names for process-intelligence-grounded AI: an
    answer with no real, linked grounding is inadmissible, not merely
    discouraged. The paper's own words, describing the failure mode this
    function's refusal prevents: "just sending textually encoded process
    variants or DFGs to the GenAI is enough to generate answers, but these
    are not very reliable." See `tests/test_epistemic_process_kernel_
    chicago.py::TestAdmitClaims` for real, direct coverage of this
    refusal."""
    admitted = []
    refused_reasons = []
    for claim in claims:
        if set(claim.source_observation_ids) <= real_obs_ids:
            admitted.append(claim)
        else:
            refused_reasons.append(
                "REFUSED:UNGROUNDED_CLAIM -- source_observation_ids not all real"
            )
    return admitted, refused_reasons


def _compute_state(hypothesis_id: str, grounded_links: list[Any]) -> str:
    """The real, deterministic state-computation rule -- the concrete
    answer to `epistemic_dspy.py`'s own design rule that DSPy never emits
    SUPPORTED/REFUTED/UNKNOWN itself. Only grounded (referentially real)
    links reach this function. Any real CONTRADICTS -> REFUTED (a single
    real contradiction is disqualifying); else any real SUPPORTS ->
    SUPPORTED; else UNKNOWN. NON_DIAGNOSTIC links never move state -- the
    structural replacement for "a fact existing for a field is not itself
    evidence that field is the fault.\""""
    own_links = [ln for ln in grounded_links if ln.hypothesis_id == hypothesis_id]
    if any(ln.relation == "CONTRADICTS" for ln in own_links):
        return "REFUTED"
    if any(ln.relation == "SUPPORTS" for ln in own_links):
        return "SUPPORTED"
    return "UNKNOWN"


def uncommitted_after_investigation(
    hypotheses: list[AdmittedHypothesis],
    all_links: list[Any],
    investigated_ids: set[str],
) -> list[AdmittedHypothesis]:
    """Real, mechanical detection of the exact gap a live run exposed: a
    hypothesis real Discriminate reads specifically targeted
    (`ReadCandidate.discriminates_hypothesis_ids`, accumulated across
    rounds by the caller) but which still has NO real evidence link at
    all -- grounded or not -- after `EvidenceLinker` ran. The model
    investigated but never committed to a verdict for it; this is the
    same shape of defect the prior architecture's `EVIDENCE_CITED_BUT_
    UNRESOLVED` check caught, applied here to this one: a hypothesis with
    real evidence-gathering already spent on it should not be allowed to
    stay silently `UNKNOWN`."""
    linked_ids = {ln.hypothesis_id for ln in all_links}
    return [
        h
        for h in hypotheses
        if h.id in investigated_ids and h.id not in linked_ids and h.state == "UNKNOWN"
    ]


def next_kernel_action(supported_count: int, unknown_count: int) -> str:
    """The real, pure, deterministic decision this session's live cluster
    run showed matters concretely: given how many hypotheses currently
    hold SUPPORTED vs. UNKNOWN, what should the kernel do next? Factored
    out of `run_episode`'s loop so this exact decision -- the concrete
    bug a real run exposed (4 SUPPORTED + 0 UNKNOWN was wrongly treated
    as done) -- is directly, deterministically testable with no LLM and
    no live cluster.

    Returns one of:
    - "closure": exactly one survivor, nothing left unresolved -- stop.
      SUPPORTED != PROVEN in general, but with exactly one SUPPORTED and
      zero UNKNOWN there is no remaining ambiguity to discriminate away.
    - "rehypothesize": every real candidate was falsified (0 SUPPORTED,
      0 UNKNOWN) -- regenerate a fresh portfolio rather than calling
      Discriminate against an empty frontier.
    - "discriminate": the frontier is still open, either under-determined
      (UNKNOWN remain) or over-determined (multiple real SUPPORTED
      survivors need something that partitions them) -- both require
      real discrimination, not just the UNKNOWN case."""
    if supported_count == 1 and unknown_count == 0:
        return "closure"
    if supported_count == 0 and unknown_count == 0:
        return "rehypothesize"
    return "discriminate"


async def run_episode(
    gym: GymAct,
    episode_id: str,
    authority_ref: str,
    goal: Goal,
    constraints: list[Constraint],
    seed_facts: list[Fact],
    *,
    read_capability_bindings: set[str],
    do_capability_bindings: set[str],
    judge_model_id: str,
    max_discriminate_rounds: int = 3,
) -> EpistemicKernelResult:
    """The real EPK sequencing loop. `seed_facts` are supplied by the
    caller (a provider-specific runner script) -- this module mints no
    fact IDs of its own during seeding, only during Discriminate.

    `read_capability_bindings`/`do_capability_bindings` are real,
    explicit, caller-supplied sets of `Capability.binding` values --
    NOT auto-derived from each capability's `Consequence`. This is a
    real, corrected generalization: an earlier version of this function
    guessed "read-like" from naming ("DO and not 'submit' in binding"),
    which happened to work for sregym (where investigatory ops like
    `run_kubectl` are declared `DO` for real authority reasons) but is
    WRONG in general -- a provider whose `DO` capabilities are genuinely
    mutating (e.g. `gymact.providers.MemoryProvider`'s `set`/`delete`/
    `increment`) would have had them wrongly exposed to `Discriminate` as
    if they were safe, non-consequential reads. Only the caller -- who
    has real domain knowledge of what each capability actually does --
    can correctly draw this line; the kernel stays fully generic by never
    guessing it. The same binding MAY appear in both sets (matching
    sregym's real `run_kubectl`: a real `DO` capability that is also the
    only way to gather new evidence)."""
    import dspy

    steps: list[KernelStep] = []
    lm = dspy.LM(judge_model_id, max_tokens=8000)

    capabilities = gym.capabilities(episode_id)
    read_capabilities = [
        _adapt_capability(c) for c in capabilities if c.binding in read_capability_bindings
    ]
    do_capabilities = [
        _adapt_capability(c) for c in capabilities if c.binding in do_capability_bindings
    ]

    facts: list[Fact] = list(seed_facts)
    next_fact_id = len(facts)
    next_obs_id = 0
    observations: dict[str, str] = {}

    with dspy.context(lm=lm):
        hypothesizer = Hypothesizer()
        prediction = hypothesizer(goal=goal, facts=facts, constraints=constraints)
    proposals = list(prediction.hypotheses)
    hypotheses: list[AdmittedHypothesis] = [
        AdmittedHypothesis(
            id=f"hyp:{i}",
            proposition=p.proposition,
            state="UNKNOWN",
            predicted_predicates=p.predicted_predicates,
            falsifier=p.falsifier,
        )
        for i, p in enumerate(proposals)
    ]
    steps.append(
        KernelStep(
            kind="hypothesize",
            payload={},
            result=[h.proposition for h in hypotheses],
        )
    )

    # Real, mechanical, accumulated-across-rounds tracking of which
    # hypotheses Discriminate has actually spent real reads investigating
    # -- feeds `uncommitted_after_investigation` below. `active_constraints`
    # is a real, mutable working copy of the caller's `constraints`; the
    # kernel appends one synthesized `Constraint` naming any hypothesis
    # left silently UNKNOWN after real investigation, the same shape as
    # `kernel_feedback` fed back on refusal in the prior architecture.
    investigated_ids: set[str] = set()
    active_constraints = list(constraints)

    rounds_used = 0
    for round_idx in range(max_discriminate_rounds):
        rounds_used = round_idx + 1
        with dspy.context(lm=lm):
            linker = EvidenceLinker()
            mapping_pred = linker(
                hypotheses=hypotheses, facts=facts, constraints=active_constraints
            )
        fact_ids = {f.id for f in facts}
        grounded_links, refused = _admit_links(list(mapping_pred.mapping.links), fact_ids)
        steps.append(
            KernelStep(
                kind="evidence_link",
                payload={"round": round_idx + 1},
                result={"grounded": len(grounded_links), "refused": refused},
            )
        )
        for h in hypotheses:
            h.state = _compute_state(h.id, grounded_links)
            h.supporting_fact_ids = [
                ln.fact_id for ln in grounded_links
                if ln.hypothesis_id == h.id and ln.relation == "SUPPORTS"
            ]
            h.contradicting_fact_ids = [
                ln.fact_id for ln in grounded_links
                if ln.hypothesis_id == h.id and ln.relation == "CONTRADICTS"
            ]

        # Real, mechanical check for the exact gap the prior architecture's
        # `EVIDENCE_CITED_BUT_UNRESOLVED` caught, applied to this one: a
        # hypothesis real Discriminate reads already targeted but which
        # `EvidenceLinker` produced NO link at all for (not even
        # NON_DIAGNOSTIC) -- investigated, never committed. Named
        # explicitly as a real `Constraint` fed into the NEXT round's
        # `EvidenceLinker` call rather than silently retried the same way.
        uncommitted = uncommitted_after_investigation(
            hypotheses, list(mapping_pred.mapping.links), investigated_ids
        )
        active_constraints = [
            c for c in active_constraints if c.id != "constraint:commit-after-investigation"
        ]
        if uncommitted:
            active_constraints.append(
                Constraint(
                    id="constraint:commit-after-investigation",
                    expression=(
                        "The following hypotheses already had real discriminating reads "
                        "executed specifically for them in a prior round, but received NO "
                        "evidence link at all (not even NON_DIAGNOSTIC) -- you MUST produce "
                        "a real link for each, even if it is NON_DIAGNOSTIC with a real "
                        "explanation of why the gathered evidence doesn't settle it: "
                        + "; ".join(f"{h.id}: {h.proposition!r}" for h in uncommitted)
                    ),
                    hard=True,
                )
            )
            steps.append(
                KernelStep(
                    kind="uncommitted_after_investigation",
                    payload={"round": round_idx + 1},
                    result=[h.id for h in uncommitted],
                )
            )

        supported = [h for h in hypotheses if h.state == "SUPPORTED"]
        unknown_hyps = [h for h in hypotheses if h.state == "UNKNOWN"]
        action = next_kernel_action(len(supported), len(unknown_hyps))

        if action == "closure":
            break

        if action == "rehypothesize":
            investigated_ids = set()
            active_constraints = [
                c for c in active_constraints
                if c.id != "constraint:commit-after-investigation"
            ]
            with dspy.context(lm=lm):
                hypothesizer = Hypothesizer()
                fresh_prediction = hypothesizer(
                    goal=goal, facts=facts, constraints=active_constraints
                )
            fresh_proposals = list(fresh_prediction.hypotheses)
            hypotheses = [
                AdmittedHypothesis(
                    id=f"hyp:r{round_idx}:{i}",
                    proposition=p.proposition,
                    state="UNKNOWN",
                    predicted_predicates=p.predicted_predicates,
                    falsifier=p.falsifier,
                )
                for i, p in enumerate(fresh_proposals)
            ]
            steps.append(
                KernelStep(
                    kind="rehypothesize",
                    payload={"round": round_idx + 1},
                    result=[h.proposition for h in hypotheses],
                )
            )
            continue

        # Otherwise the epistemic frontier is still open -- either
        # under-determined (UNKNOWN remain) or over-determined (multiple
        # real SUPPORTED survivors need something that partitions them).
        # Both require real discrimination, not just the UNKNOWN case.
        survivors = supported + unknown_hyps
        obligations = list(mapping_pred.mapping.obligations)

        with dspy.context(lm=lm):
            discriminator = Discriminator()
            disc_pred = discriminator(
                goal=goal,
                facts=facts,
                hypotheses=survivors,
                obligations=obligations,
                read_capabilities=read_capabilities,
            )
        candidates: list[ReadCandidate] = list(disc_pred.candidates)
        if not candidates:
            # Discriminator genuinely found nothing further to check --
            # stop rather than loop forever; the frontier stays open and
            # is refused honestly below (never a forced single winner).
            break
        real_capability_ids = {c.id for c in read_capabilities}

        for candidate in candidates:
            gymact_cap = _find_gymact_capability(capabilities, candidate.capability_id)
            if gymact_cap is None or candidate.capability_id not in real_capability_ids:
                steps.append(
                    KernelStep(
                        kind="discriminate_refused",
                        payload={"capability_id": candidate.capability_id},
                        result="REFUSED:UNKNOWN_CAPABILITY -- not a real capability_id "
                        "from read_capabilities",
                    )
                )
                continue
            outcome = await _execute_capability(
                gym, episode_id, authority_ref, gymact_cap, candidate.parameters
            )
            obs_id = f"obs:{next_obs_id}"
            next_obs_id += 1
            observations[obs_id] = str(outcome["effect"])
            investigated_ids.update(candidate.discriminates_hypothesis_ids)
            steps.append(
                KernelStep(
                    kind="discriminate_execute",
                    payload={"capability_id": candidate.capability_id,
                              "parameters": candidate.parameters},
                    result={"observation_id": obs_id, "outcome": outcome},
                )
            )

        if observations:
            with dspy.context(lm=lm):
                extractor = CandidateClaimExtractor()
                claims_pred = extractor(
                    observation_text_by_id=observations, existing_facts=facts
                )
            # Same "No AI Without PI!" (arXiv:2508.00116) grounding
            # requirement as `_admit_links` above, applied to claim
            # extraction via `_admit_claims`.
            real_obs_ids = set(observations.keys())
            admitted_claims, refused_claim_reasons = _admit_claims(
                list(claims_pred.claims), real_obs_ids
            )
            admitted_claim_ids = {id(c) for c in admitted_claims}
            refused_claims = [
                c for c in claims_pred.claims if id(c) not in admitted_claim_ids
            ]
            for claim, reason in zip(refused_claims, refused_claim_reasons, strict=True):
                steps.append(
                    KernelStep(
                        kind="claim_refused",
                        payload={"subject": claim.subject, "predicate": claim.predicate},
                        result=reason,
                    )
                )
            for claim in admitted_claims:
                fact = Fact(
                    id=f"fact:{next_fact_id}",
                    subject=claim.subject,
                    predicate=claim.predicate,
                    value=claim.value,
                    source_observation_ids=claim.source_observation_ids,
                )
                next_fact_id += 1
                facts.append(fact)
                steps.append(
                    KernelStep(kind="fact_admitted", payload={}, result=fact.model_dump())
                )

    supported = [h for h in hypotheses if h.state == "SUPPORTED"]
    if len(supported) != 1:
        names = [h.proposition for h in supported]
        reason = (
            f"REFUSED:NO_SUPPORTED_HYPOTHESIS -- no hypothesis reached SUPPORTED after "
            f"{rounds_used} round(s)"
            if not supported
            else f"REFUSED:MULTIPLE_SUPPORTED_HYPOTHESES -- {names!r}, a real diagnosis "
            "names exactly one root cause"
        )
        return EpistemicKernelResult(
            admitted=False,
            admission_reason=reason,
            diagnosis=None,
            selected_plan=None,
            facts=facts,
            hypotheses=hypotheses,
            rounds_used=rounds_used,
            steps=steps,
        )

    with dspy.context(lm=lm):
        diagnoser = Diagnoser()
        diag_pred = diagnoser(goal=goal, facts=facts, hypotheses=hypotheses)
    diagnosis: DiagnosisCandidate = diag_pred.diagnosis
    if set(diagnosis.supported_hypothesis_ids) != {supported[0].id}:
        return EpistemicKernelResult(
            admitted=False,
            admission_reason="REFUSED:DIAGNOSIS_DIVERGES_FROM_ADMITTED_STATE -- "
            f"diagnosis names {diagnosis.supported_hypothesis_ids!r} but the kernel "
            f"computed exactly {supported[0].id!r} as SUPPORTED",
            diagnosis=diagnosis,
            selected_plan=None,
            facts=facts,
            hypotheses=hypotheses,
            rounds_used=rounds_used,
            steps=steps,
        )
    steps.append(KernelStep(kind="diagnose", payload={}, result=diagnosis.model_dump()))

    with dspy.context(lm=lm):
        constructor = PlanConstructor()
        plan_pred = constructor(
            goal=goal,
            diagnosis=diagnosis,
            facts=facts,
            constraints=constraints,
            do_capabilities=do_capabilities,
        )
    plans: list[CandidatePlan] = list(plan_pred.plans)
    real_do_ids = {c.id for c in do_capabilities}
    selected_plan = next(
        (p for p in plans if all(step.capability_id in real_do_ids for step in p.steps)),
        None,
    )
    if selected_plan is None:
        return EpistemicKernelResult(
            admitted=False,
            admission_reason="REFUSED:NO_VALID_PLAN -- no candidate plan referenced only "
            "real do_capabilities",
            diagnosis=diagnosis,
            selected_plan=None,
            facts=facts,
            hypotheses=hypotheses,
            rounds_used=rounds_used,
            steps=steps,
        )
    steps.append(
        KernelStep(kind="construct", payload={}, result=selected_plan.model_dump())
    )

    diagnosis_submitted = False
    mitigation_submitted = False
    for plan_step in selected_plan.steps:
        gymact_cap = _find_gymact_capability(capabilities, plan_step.capability_id)
        if gymact_cap is None:
            continue
        outcome = await _execute_capability(
            gym, episode_id, authority_ref, gymact_cap, plan_step.parameters
        )
        steps.append(
            KernelStep(
                kind="brce_act",
                payload={"capability_id": plan_step.capability_id,
                          "parameters": plan_step.parameters},
                result=outcome,
            )
        )
        if "diagnosis" in gymact_cap.binding:
            diagnosis_submitted = bool(outcome["accepted"])
        if "mitigation" in gymact_cap.binding:
            mitigation_submitted = bool(outcome["accepted"])

    return EpistemicKernelResult(
        admitted=True,
        admission_reason=f"ADMITTED -- {supported[0].proposition!r} is the sole "
        "supported hypothesis",
        diagnosis=diagnosis,
        selected_plan=selected_plan,
        facts=facts,
        hypotheses=hypotheses,
        diagnosis_submitted=diagnosis_submitted,
        mitigation_submitted=mitigation_submitted,
        rounds_used=rounds_used,
        steps=steps,
    )


async def explain_episode(
    result: EpistemicKernelResult,
    goal: Goal,
    *,
    judge_model_id: str,
) -> tuple[str, str]:
    """Run the real tutor-explanation pass over an episode's actual
    outcome. Returns `(lesson, why)`. Safe to call on a refused episode --
    that is its whole reason for existing."""
    import dspy

    class ExplainRun(dspy.Signature):
        """You are a senior Kubernetes SRE mentoring a colleague by walking
        them through a real diagnostic episode's actual trace -- not a
        finished postmortem, a real teaching pass over what was tried.

        Never fabricate a root cause the episode did not itself admit.
        If `admitted` is False, say so plainly and explain WHY, grounded
        only in `admission_reason` and the real hypotheses/facts given --
        do not invent evidence that wasn't gathered, and do not soften an
        open question into a false conclusion. Name concretely: (1) which
        real hypotheses were considered and what real evidence was
        actually gathered for each (or the real reason none was), (2) any
        real structural gap visible in the evidence itself (e.g. a query
        convention that returned nothing, a real tool error) worth
        flagging as its own lesson, (3) what a senior engineer would
        concretely investigate next, and why -- tied to the real facts
        given, not generic advice that would apply to any incident."""

        goal: Goal = dspy.InputField(desc="the desired state the episode was pursuing")
        hypotheses: list[AdmittedHypothesis] = dspy.InputField(
            desc="the real hypotheses considered during the episode, kernel-computed state "
            "included"
        )
        facts: list[Fact] = dspy.InputField(
            desc="the real facts gathered and admitted during the episode"
        )
        admitted: bool = dspy.InputField(
            desc="whether the kernel actually admitted a diagnosis for this episode"
        )
        admission_reason: str = dspy.InputField(
            desc="the kernel's real, specific reason the episode was admitted or refused"
        )
        rounds_used: int = dspy.InputField(
            desc="how many real discrimination/evidence rounds the episode actually used"
        )
        lesson: str = dspy.OutputField(
            desc="a real, structured mentoring narrative grounded only in the given "
            "hypotheses/facts/admission_reason -- never fabricated"
        )
        why: str = dspy.OutputField(
            desc="explicit justification tying the lesson's specific recommendations "
            "back to the real facts/hypotheses given"
        )

    lm = dspy.LM(judge_model_id, max_tokens=6000)
    with dspy.context(lm=lm):
        prediction = await dspy.ChainOfThought(ExplainRun).acall(
            goal=goal,
            hypotheses=result.hypotheses,
            facts=result.facts,
            admitted=result.admitted,
            admission_reason=result.admission_reason,
            rounds_used=result.rounds_used,
        )
    return prediction.lesson, prediction.why
