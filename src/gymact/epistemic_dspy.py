# ruff: noqa: RUF022 -- __all__ is intentionally grouped (substrate/signatures/modules), not alphabetical
"""
Domain-general DSPy cognitive operators for the GymAct Epistemic Process Kernel.

Design rule
===========
DSPy implements typed cognitive morphisms. It does NOT own:
- the process loop,
- tool execution,
- phase transitions,
- canonical Fact IDs,
- epistemic state admission,
- action authority,
- actuation,
- verification standing.

The external Epistemic Process Kernel (EPK) chooses which operator runs.
The domain adapter / capability graph supplies provider-specific READ/DO
capabilities (Kubernetes, GCP, AWS, Azure, Terraform, etc.).

There is intentionally:
- no hard-coded fault/category list,
- no fixed Kubernetes field list,
- no raw kubectl/shell tool,
- no record_fact tool,
- no finish tool,
- no dspy.ReAct process controller.

Compatible with the modern DSPy 3.x programming style:
typed dspy.Signature + dspy.Predict / dspy.ChainOfThought + dspy.Module.
"""

from __future__ import annotations

from typing import Any, Literal

import dspy
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Canonical substrate types
# ---------------------------------------------------------------------------

EpistemicState = Literal["UNKNOWN", "SUPPORTED", "REFUTED"]
EvidenceRelation = Literal["SUPPORTS", "CONTRADICTS", "NON_DIAGNOSTIC"]
Consequence = Literal["READ", "DO"]
ClaimRelation = Literal["ASSERTS", "DENIES"]
PlanRisk = Literal["LOW", "MEDIUM", "HIGH"]


class Fact(BaseModel):
    """A fact already admitted by the kernel.

    DSPy may reference Fact.id but must never mint canonical Fact IDs.
    """

    id: str
    subject: str
    predicate: str
    value: str
    source_observation_ids: list[str] = Field(default_factory=list)
    derivation_ids: list[str] = Field(default_factory=list)


class Constraint(BaseModel):
    """A law, invariant, policy, requirement, or architectural constraint."""

    id: str
    expression: str
    source_ids: list[str] = Field(default_factory=list)
    hard: bool = True


class Goal(BaseModel):
    """Desired state expressed independently of any provider implementation."""

    id: str
    desired_predicates: list[str]
    prohibited_predicates: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class Capability(BaseModel):
    """A domain-adapter capability.

    Examples are supplied at runtime by the capability graph. The DSPy program
    sees capability IDs and schemas; it does not invent raw provider commands.
    """

    id: str
    consequence: Consequence
    description: str
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    authority_scope: list[str] = Field(default_factory=list)
    estimated_cost: float | None = None
    estimated_latency_ms: float | None = None
    risk: PlanRisk = "LOW"


class ScenarioFrame(BaseModel):
    """Candidate semantic framing of an unstructured task/scenario."""

    goal: Goal
    candidate_constraints: list[Constraint] = Field(default_factory=list)
    unresolved_terms: list[str] = Field(default_factory=list)


class CandidateClaim(BaseModel):
    """A non-canonical claim extracted from unstructured evidence.

    The kernel/domain adapter must validate this against source observations
    before it may become a canonical Fact.
    """

    subject: str
    predicate: str
    value: str
    relation: ClaimRelation = "ASSERTS"
    source_observation_ids: list[str]
    rationale: str


class HypothesisProposal(BaseModel):
    """A candidate causal explanation, not yet an admitted hypothesis."""

    proposition: str
    scope_refs: list[str] = Field(default_factory=list)
    predicted_predicates: list[str] = Field(default_factory=list)
    falsifier: str
    assumptions: list[str] = Field(default_factory=list)


class AdmittedHypothesis(BaseModel):
    """Kernel-owned hypothesis record supplied back to DSPy.

    `state` is computed/admitted outside the LM.
    """

    id: str
    proposition: str
    state: EpistemicState
    # Carried forward from the real `HypothesisProposal` that produced this
    # record -- a real, live run showed `EvidenceLinker` guessing relevance
    # without ever seeing what would actually falsify a hypothesis, or what
    # predicate it predicts. Without these, "NON_DIAGNOSTIC" (the docstring's
    # own stated bar for merely-adjacent facts) has no real test to apply;
    # with them, a fact can be checked against a real, stated predicate
    # instead of judged on plausibility alone.
    predicted_predicates: list[str] = Field(default_factory=list)
    falsifier: str = ""
    supporting_fact_ids: list[str] = Field(default_factory=list)
    contradicting_fact_ids: list[str] = Field(default_factory=list)
    unresolved_obligations: list[str] = Field(default_factory=list)


class EvidenceLinkProposal(BaseModel):
    """LM-proposed interpretation of how one admitted fact bears on a hypothesis.

    The kernel / wasm4pm reasoner validates the IDs and computes state.
    """

    hypothesis_id: str
    fact_id: str
    relation: EvidenceRelation
    why: str


class EpistemicObligation(BaseModel):
    """Something that must be observed/derived before uncertainty can collapse."""

    hypothesis_id: str
    required_predicate: str
    why_required: str


class EvidenceMapping(BaseModel):
    links: list[EvidenceLinkProposal] = Field(default_factory=list)
    obligations: list[EpistemicObligation] = Field(default_factory=list)


class ReadCandidate(BaseModel):
    """An abstract READ intent candidate.

    No shell/kubectl/provider command appears here. The domain adapter maps the
    capability_id + parameters into the provider-specific operation.
    """

    capability_id: str
    target_refs: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    obligation_indexes: list[int] = Field(default_factory=list)
    discriminates_hypothesis_ids: list[str] = Field(default_factory=list)
    expected_partition: str
    why_discriminating: str


class DiagnosisCandidate(BaseModel):
    """A causal commitment candidate constructed only from admitted hypotheses."""

    supported_hypothesis_ids: list[str]
    unresolved_competitor_ids: list[str] = Field(default_factory=list)
    causal_chain: list[str]
    explanation: str


class PlanStep(BaseModel):
    """One abstract consequential transition.

    The kernel admits each step before BRCE can actuate it.
    """

    capability_id: str
    target_refs: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_fact_ids: list[str] = Field(default_factory=list)
    expected_effect_predicates: list[str] = Field(default_factory=list)
    rollback_capability_id: str | None = None
    rollback_parameters: dict[str, Any] = Field(default_factory=dict)


class CandidatePlan(BaseModel):
    """One reversible candidate plan in the CMD portfolio."""

    name: str
    steps: list[PlanStep]
    satisfies_goal_predicates: list[str]
    preserves_constraints: list[str]
    verification_predicates: list[str]
    reversibility: Literal["FULL", "PARTIAL", "NONE"]
    risk: PlanRisk
    tradeoffs: list[str] = Field(default_factory=list)


class VerificationAssessment(BaseModel):
    """Interpretation-only result; final verification standing remains kernel-owned."""

    satisfied_predicates: list[str] = Field(default_factory=list)
    violated_predicates: list[str] = Field(default_factory=list)
    unknown_predicates: list[str] = Field(default_factory=list)
    supporting_fact_ids: list[str] = Field(default_factory=list)
    explanation: str


class ReceiptExplanation(BaseModel):
    summary: str
    causal_result: str
    residual_uncertainty: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# DSPy signatures: atomic cognitive morphisms
# ---------------------------------------------------------------------------


class FrameScenario(dspy.Signature):
    """Frame an unstructured incident, architecture exercise, or certification
    scenario as provider-neutral desired predicates and constraints.

    Do not select a cloud provider, Kubernetes object, product, or remediation.
    Do not invent observations. This is semantic framing only.
    """

    scenario: str = dspy.InputField(
        desc="the raw unstructured incident/architecture/certification text to frame"
    )
    admitted_facts: list[Fact] = dspy.InputField(
        desc="facts already admitted by the kernel; use only to disambiguate framing, "
        "never as license to select a provider or remediation"
    )
    known_constraints: list[Constraint] = dspy.InputField(
        desc="constraints already known to the kernel before framing"
    )

    frame: ScenarioFrame = dspy.OutputField(
        desc="provider-neutral desired predicates, candidate constraints, and unresolved "
        "terms extracted from scenario"
    )


class ExtractCandidateClaims(dspy.Signature):
    """Extract checkable claims from genuinely unstructured observations.

    Use only when mechanical/domain-specific extraction is unavailable.
    Every claim MUST cite one or more source_observation_ids. These outputs are
    candidates only; the kernel decides whether they become Facts.
    """

    observation_text_by_id: dict[str, str] = dspy.InputField(
        desc="observation_id -> raw unstructured observation text to extract claims from"
    )
    existing_facts: list[Fact] = dspy.InputField(
        desc="facts already admitted by the kernel, to avoid re-extracting duplicates"
    )

    claims: list[CandidateClaim] = dspy.OutputField(
        desc="candidate claims, each citing at least one source_observation_id verbatim "
        "from observation_text_by_id"
    )


class GenerateHypothesisPortfolio(dspy.Signature):
    """Construct a diverse causal hypothesis portfolio from admitted facts,
    constraints, and the goal.

    Do not use a fixed fault taxonomy. Do not treat mere difference/rarity as a
    fault unless a constraint, goal, relation, or causal prediction makes the
    difference diagnostically relevant. Prefer hypotheses with distinct
    falsifiers and distinct predicted observations.
    """

    goal: Goal = dspy.InputField(desc="the desired state this diagnosis must explain a gap toward")
    facts: list[Fact] = dspy.InputField(desc="facts already admitted by the kernel")
    constraints: list[Constraint] = dspy.InputField(
        desc="laws/invariants/policies the hypotheses must remain consistent with"
    )

    hypotheses: list[HypothesisProposal] = dspy.OutputField(
        desc="a diverse portfolio of candidate causal explanations, each with its own "
        "distinct falsifier and predicted_predicates"
    )


class MapEvidenceToHypotheses(dspy.Signature):
    """Map admitted facts to hypotheses and expose missing epistemic obligations.

    IMPORTANT: Do NOT output SUPPORTED/REFUTED/UNKNOWN. The LM proposes evidence
    relations; the kernel / deterministic reasoner computes epistemic state.
    A fact that is merely adjacent to a hypothesis must be NON_DIAGNOSTIC.

    Each hypothesis carries its own real `predicted_predicates` and
    `falsifier` (from when it was proposed). Use these as the actual test:
    a fact only SUPPORTS a hypothesis if it evaluates one of that
    hypothesis's own `predicted_predicates` in its favor; a fact only
    CONTRADICTS if it matches (or logically implies) that hypothesis's own
    `falsifier`. A fact that is plausible-sounding but does not evaluate
    that specific hypothesis's own predicted_predicates/falsifier is
    NON_DIAGNOSTIC, even if it looks relevant. Two hypotheses that both
    claim to explain the same real symptom are NOT automatically both
    SUPPORTED merely because each cites some real fact -- actively check
    whether evidence relevant to one hypothesis's falsifier also bears on
    (and should CONTRADICT) a competing hypothesis that predicts something
    incompatible with it.
    """

    hypotheses: list[AdmittedHypothesis] = dspy.InputField(
        desc="kernel-admitted hypotheses, each with its own real predicted_predicates "
        "and falsifier to test facts against"
    )
    facts: list[Fact] = dspy.InputField(desc="facts already admitted by the kernel")
    constraints: list[Constraint] = dspy.InputField(
        desc="laws/invariants/policies relevant to judging evidence relations"
    )

    mapping: EvidenceMapping = dspy.OutputField(
        desc="proposed SUPPORTS/CONTRADICTS/NON_DIAGNOSTIC links between facts and "
        "hypotheses, plus any unresolved epistemic obligations"
    )


class ProposeDiscriminatingReads(dspy.Signature):
    """Construct a portfolio of lawful READ intents for unresolved obligations.

    Use only capabilities explicitly present in read_capabilities.
    Reference capability_id verbatim. Do not invent provider commands.
    Prefer observations that partition surviving hypotheses differently.
    Do not rank by fabricated numeric scores; the kernel/wasm4pm may rank using
    real cost, latency, risk, and expected information gain.
    """

    goal: Goal = dspy.InputField(desc="the desired state driving which unknowns matter")
    facts: list[Fact] = dspy.InputField(desc="facts already admitted by the kernel")
    hypotheses: list[AdmittedHypothesis] = dspy.InputField(
        desc="surviving kernel-admitted hypotheses the reads should discriminate between"
    )
    obligations: list[EpistemicObligation] = dspy.InputField(
        desc="unresolved epistemic obligations naming what must still be observed"
    )
    read_capabilities: list[Capability] = dspy.InputField(
        desc="the ONLY lawful READ capabilities available; reference capability_id "
        "verbatim, never invent a provider command"
    )

    candidates: list[ReadCandidate] = dspy.OutputField(
        desc="candidate READ intents, each explaining why_discriminating and which "
        "hypotheses it partitions"
    )


class CommitDiagnosis(dspy.Signature):
    """Construct a diagnosis candidate from KERNEL-COMPUTED hypothesis states.

    Every selected hypothesis must already be SUPPORTED. Surface unresolved
    competitors rather than silently converting UNKNOWN into false.
    This output is still only a candidate; the diagnosis admission gate decides
    whether causal commitment is allowed.
    """

    goal: Goal = dspy.InputField(desc="the desired state the diagnosis must explain a gap toward")
    facts: list[Fact] = dspy.InputField(desc="facts already admitted by the kernel")
    hypotheses: list[AdmittedHypothesis] = dspy.InputField(
        desc="kernel-computed hypotheses; only ones whose state is SUPPORTED may be "
        "selected into the diagnosis"
    )

    diagnosis: DiagnosisCandidate = dspy.OutputField(
        desc="a causal commitment built only from SUPPORTED hypotheses, naming any "
        "unresolved competitors rather than silently dropping them"
    )


class ConstructPlanPortfolio(dspy.Signature):
    """Construct several reversible plans from an ADMITTED diagnosis.

    Use only supplied DO capability IDs. Preserve hard constraints. Represent
    provider-specific operations as capability_id + typed parameters, never raw
    shell commands. Include expected effects, rollback, and verification
    predicates for every plan. Do not select or execute a winner.
    """

    goal: Goal = dspy.InputField(desc="the desired state every plan must satisfy")
    diagnosis: DiagnosisCandidate = dspy.InputField(
        desc="the admitted diagnosis every plan must remediate"
    )
    facts: list[Fact] = dspy.InputField(desc="facts already admitted by the kernel")
    constraints: list[Constraint] = dspy.InputField(
        desc="hard constraints every plan must preserve"
    )
    do_capabilities: list[Capability] = dspy.InputField(
        desc="the ONLY lawful DO capabilities available; reference capability_id "
        "verbatim, never invent a raw shell/provider command"
    )

    plans: list[CandidatePlan] = dspy.OutputField(
        desc="several reversible candidate plans, each with expected effects, rollback, "
        "and verification predicates; do not select a winner"
    )


class InterpretVerificationEvidence(dspy.Signature):
    """Interpret post-actuation admitted facts against explicit verification
    predicates.

    This does not grant VERIFIED standing. The kernel checks referential
    integrity, convergence, safety/regression criteria, and receipt evidence.
    """

    expected_predicates: list[str] = dspy.InputField(
        desc="the explicit predicates the selected plan committed to satisfying"
    )
    post_action_facts: list[Fact] = dspy.InputField(
        desc="facts admitted by the kernel after actuation, to check against "
        "expected_predicates"
    )
    safety_constraints: list[Constraint] = dspy.InputField(
        desc="hard constraints post-action facts must not violate"
    )

    assessment: VerificationAssessment = dspy.OutputField(
        desc="which expected_predicates are satisfied/violated/unknown given "
        "post_action_facts, grounded in supporting_fact_ids; does not itself grant "
        "VERIFIED standing"
    )


class ExplainReceipt(dspy.Signature):
    """Produce a human-readable explanation from already-admitted execution and
    verification records. Explanation has no authority to change standing.
    """

    diagnosis: DiagnosisCandidate = dspy.InputField(desc="the admitted diagnosis to explain")
    selected_plan: CandidatePlan = dspy.InputField(
        desc="the plan the kernel actually selected and actuated"
    )
    execution_fact_ids: list[str] = dspy.InputField(
        desc="fact ids the kernel admitted while actuating selected_plan"
    )
    verification: VerificationAssessment = dspy.InputField(
        desc="the kernel's already-computed verification assessment for this run"
    )

    explanation: ReceiptExplanation = dspy.OutputField(
        desc="a human-readable summary of the causal result and any residual "
        "uncertainty, grounded only in the already-admitted records given"
    )


# ---------------------------------------------------------------------------
# DSPy modules: one bounded operator each
# ---------------------------------------------------------------------------


class ScenarioFramer(dspy.Module):
    """Optional semantic boundary for natural-language tasks/cert questions."""

    def __init__(self) -> None:
        super().__init__()
        self.frame = dspy.ChainOfThought(FrameScenario)

    def forward(
        self,
        scenario: str,
        admitted_facts: list[Fact],
        known_constraints: list[Constraint],
    ) -> dspy.Prediction:
        return self.frame(
            scenario=scenario,
            admitted_facts=admitted_facts,
            known_constraints=known_constraints,
        )


class CandidateClaimExtractor(dspy.Module):
    """Optional bounded extractor for unstructured observations only."""

    def __init__(self) -> None:
        super().__init__()
        self.extract = dspy.Predict(ExtractCandidateClaims)

    def forward(
        self,
        observation_text_by_id: dict[str, str],
        existing_facts: list[Fact],
    ) -> dspy.Prediction:
        return self.extract(
            observation_text_by_id=observation_text_by_id,
            existing_facts=existing_facts,
        )


class Hypothesizer(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.generate = dspy.ChainOfThought(GenerateHypothesisPortfolio)

    def forward(
        self,
        goal: Goal,
        facts: list[Fact],
        constraints: list[Constraint],
    ) -> dspy.Prediction:
        return self.generate(goal=goal, facts=facts, constraints=constraints)


class EvidenceLinker(dspy.Module):
    """Proposes evidence links; deliberately cannot set epistemic state."""

    def __init__(self) -> None:
        super().__init__()
        self.map = dspy.ChainOfThought(MapEvidenceToHypotheses)

    def forward(
        self,
        hypotheses: list[AdmittedHypothesis],
        facts: list[Fact],
        constraints: list[Constraint],
    ) -> dspy.Prediction:
        return self.map(
            hypotheses=hypotheses,
            facts=facts,
            constraints=constraints,
        )


class Discriminator(dspy.Module):
    """Constructs READ alternatives; does not execute or select them."""

    def __init__(self) -> None:
        super().__init__()
        self.propose = dspy.ChainOfThought(ProposeDiscriminatingReads)

    def forward(
        self,
        goal: Goal,
        facts: list[Fact],
        hypotheses: list[AdmittedHypothesis],
        obligations: list[EpistemicObligation],
        read_capabilities: list[Capability],
    ) -> dspy.Prediction:
        return self.propose(
            goal=goal,
            facts=facts,
            hypotheses=hypotheses,
            obligations=obligations,
            read_capabilities=read_capabilities,
        )


class Diagnoser(dspy.Module):
    """Produces a diagnosis candidate only from externally computed states."""

    def __init__(self) -> None:
        super().__init__()
        self.commit = dspy.ChainOfThought(CommitDiagnosis)

    def forward(
        self,
        goal: Goal,
        facts: list[Fact],
        hypotheses: list[AdmittedHypothesis],
    ) -> dspy.Prediction:
        return self.commit(goal=goal, facts=facts, hypotheses=hypotheses)


class PlanConstructor(dspy.Module):
    """CMD operator: manufactures a portfolio; never actuates."""

    def __init__(self) -> None:
        super().__init__()
        self.construct = dspy.ChainOfThought(ConstructPlanPortfolio)

    def forward(
        self,
        goal: Goal,
        diagnosis: DiagnosisCandidate,
        facts: list[Fact],
        constraints: list[Constraint],
        do_capabilities: list[Capability],
    ) -> dspy.Prediction:
        return self.construct(
            goal=goal,
            diagnosis=diagnosis,
            facts=facts,
            constraints=constraints,
            do_capabilities=do_capabilities,
        )


class VerificationInterpreter(dspy.Module):
    """Interpretation only; the kernel owns VERIFIED standing."""

    def __init__(self) -> None:
        super().__init__()
        self.interpret = dspy.ChainOfThought(InterpretVerificationEvidence)

    def forward(
        self,
        expected_predicates: list[str],
        post_action_facts: list[Fact],
        safety_constraints: list[Constraint],
    ) -> dspy.Prediction:
        return self.interpret(
            expected_predicates=expected_predicates,
            post_action_facts=post_action_facts,
            safety_constraints=safety_constraints,
        )


class ReceiptExplainer(dspy.Module):
    """Pure explanation from admitted records."""

    def __init__(self) -> None:
        super().__init__()
        self.explain = dspy.Predict(ExplainReceipt)

    def forward(
        self,
        diagnosis: DiagnosisCandidate,
        selected_plan: CandidatePlan,
        execution_fact_ids: list[str],
        verification: VerificationAssessment,
    ) -> dspy.Prediction:
        return self.explain(
            diagnosis=diagnosis,
            selected_plan=selected_plan,
            execution_fact_ids=execution_fact_ids,
            verification=verification,
        )


# ---------------------------------------------------------------------------
# Convenience construction
# ---------------------------------------------------------------------------


def build_cognitive_operators() -> dict[str, dspy.Module]:
    """Return atomic DSPy operators keyed by the EPK phase that may invoke them.

    The EPK owns sequencing, e.g.:

        O -> O*                           # mechanical/domain adapter
        HYPOTHESIZE -> Hypothesizer
        EVIDENCE_LINK -> EvidenceLinker
        [kernel / wasm computes states]
        DISCRIMINATE -> Discriminator
        [kernel selects + executes READ capability]
        ...
        DIAGNOSE -> Diagnoser
        [kernel admits diagnosis]
        CONSTRUCT -> PlanConstructor
        [kernel dry-run / policy / SAT / Pareto selection]
        BRCE -> DO                        # never DSPy
        VERIFY -> VerificationInterpreter
        [kernel grants standing + receipt]
        EXPLAIN -> ReceiptExplainer

    The dictionary is deliberately not an autonomous agent loop.
    """

    return {
        "FRAME": ScenarioFramer(),
        "EXTRACT_CANDIDATE_CLAIMS": CandidateClaimExtractor(),
        "HYPOTHESIZE": Hypothesizer(),
        "EVIDENCE_LINK": EvidenceLinker(),
        "DISCRIMINATE": Discriminator(),
        "DIAGNOSE": Diagnoser(),
        "CONSTRUCT": PlanConstructor(),
        "INTERPRET_VERIFICATION": VerificationInterpreter(),
        "EXPLAIN_RECEIPT": ReceiptExplainer(),
    }


__all__ = [
    # substrate
    "Fact",
    "Constraint",
    "Goal",
    "Capability",
    "ScenarioFrame",
    "CandidateClaim",
    "HypothesisProposal",
    "AdmittedHypothesis",
    "EvidenceLinkProposal",
    "EpistemicObligation",
    "EvidenceMapping",
    "ReadCandidate",
    "DiagnosisCandidate",
    "PlanStep",
    "CandidatePlan",
    "VerificationAssessment",
    "ReceiptExplanation",
    # signatures
    "FrameScenario",
    "ExtractCandidateClaims",
    "GenerateHypothesisPortfolio",
    "MapEvidenceToHypotheses",
    "ProposeDiscriminatingReads",
    "CommitDiagnosis",
    "ConstructPlanPortfolio",
    "InterpretVerificationEvidence",
    "ExplainReceipt",
    # modules
    "ScenarioFramer",
    "CandidateClaimExtractor",
    "Hypothesizer",
    "EvidenceLinker",
    "Discriminator",
    "Diagnoser",
    "PlanConstructor",
    "VerificationInterpreter",
    "ReceiptExplainer",
    "build_cognitive_operators",
]
