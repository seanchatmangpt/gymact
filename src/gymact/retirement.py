"""Evidence-bounded retirement controller for recurring general-LLM work.

This module composes existing GymAct compile-out machinery. It does not execute
capabilities, grant authority, or invent deterministic recipes. Its only job is
to decide whether a recurring equivalence class has enough admitted evidence
for the general-LLM path to leave the normal control loop.

Retirement is scoped to one exact RecipeIdentity. Novel subjects still route
through COLD intelligence.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from gymact.compileout import (
    CompiledRecipe,
    RecipeAdmission,
    RecipeIdentity,
    admit_compiled_recipe,
    compile_recipe,
)
from gymact.evidence import digest
from gymact.intelligence import (
    CognitionEpisode,
    CompilationCandidate,
    CompileOutObservation,
    detect_compilation_candidate,
)
from gymact.models import FrozenModel, Standing


class RetirementDisposition(StrEnum):
    RETAIN_GENERAL_LLM = "RETAIN_GENERAL_LLM"
    SHADOW_DETERMINISTIC = "SHADOW_DETERMINISTIC"
    RETIRE_GENERAL_LLM = "RETIRE_GENERAL_LLM"


class ResidualWorkProfile(FrozenModel):
    """Normalized recurring-work terms.

    ratio = (phi*eta + (1-phi)*mu + rework + automation_support)
            / (1 + baseline_overhead)
    """

    exception_share: float = Field(ge=0.0, le=1.0)
    exception_effort_multiplier: float = Field(ge=0.0)
    ordinary_review_multiplier: float = Field(ge=0.0)
    rework: float = Field(ge=0.0)
    automation_support: float = Field(ge=0.0)
    baseline_overhead: float = Field(ge=0.0)

    @property
    def ratio(self) -> float:
        numerator = (
            self.exception_share * self.exception_effort_multiplier
            + (1.0 - self.exception_share) * self.ordinary_review_multiplier
            + self.rework
            + self.automation_support
        )
        return numerator / (1.0 + self.baseline_overhead)


class RetirementDecision(FrozenModel):
    disposition: RetirementDisposition
    standing: Standing
    general_llm_required: bool
    deterministic_candidate_ref: str | None = None
    residual_work_ratio: float
    reason: str


class RetirementReceipt(FrozenModel):
    """Content-addressed evidence for one retirement decision."""

    recipe_digest: str
    source_receipt_refs: tuple[str, ...]
    cold_receipt_ref: str
    hot_receipt_ref: str
    information_sufficient: bool
    residual_work_ratio: float
    decision: RetirementDecision
    receipt_digest: str


def evaluate_retirement(
    recipe: CompiledRecipe,
    admission: RecipeAdmission,
    observation: CompileOutObservation,
    residual_work: ResidualWorkProfile,
    *,
    information_sufficient: bool,
    max_residual_work_ratio: float,
    minimum_source_receipts: int = 2,
) -> RetirementDecision:
    """Classify retirement of the recurring general-LLM path.

    This is deliberately stricter than HOT selection. A HOT candidate can be
    useful while the general model remains available; retirement additionally
    requires sufficient information, verified compile-out, repeated source
    receipts, and an explicit residual-work threshold.
    """
    if not 0.0 <= max_residual_work_ratio <= 1.0:
        raise ValueError("MAX_RESIDUAL_WORK_RATIO_MUST_BE_IN_0_1")
    if minimum_source_receipts < 2:
        raise ValueError("MINIMUM_SOURCE_RECEIPTS_MUST_BE_AT_LEAST_TWO")

    if not information_sufficient:
        return RetirementDecision(
            disposition=RetirementDisposition.RETAIN_GENERAL_LLM,
            standing=Standing.BLOCKED,
            general_llm_required=True,
            residual_work_ratio=residual_work.ratio,
            reason="EVIDENCE_CEILING",
        )

    if not admission.admitted or admission.model_required:
        return RetirementDecision(
            disposition=RetirementDisposition.RETAIN_GENERAL_LLM,
            standing=admission.standing,
            general_llm_required=True,
            residual_work_ratio=residual_work.ratio,
            reason=f"HOT_RECIPE_NOT_ADMITTED:{admission.reason}",
        )

    if not observation.compiled_out:
        return RetirementDecision(
            disposition=RetirementDisposition.RETAIN_GENERAL_LLM,
            standing=Standing.PARTIAL_ALIVE,
            general_llm_required=True,
            deterministic_candidate_ref=admission.candidate_ref,
            residual_work_ratio=residual_work.ratio,
            reason="COMPILE_OUT_NOT_PROVEN",
        )

    if len(recipe.source_receipt_refs) < minimum_source_receipts:
        return RetirementDecision(
            disposition=RetirementDisposition.SHADOW_DETERMINISTIC,
            standing=Standing.PARTIAL_ALIVE,
            general_llm_required=True,
            deterministic_candidate_ref=admission.candidate_ref,
            residual_work_ratio=residual_work.ratio,
            reason="INSUFFICIENT_RECURRENT_RECEIPTS",
        )

    if residual_work.ratio > max_residual_work_ratio:
        return RetirementDecision(
            disposition=RetirementDisposition.SHADOW_DETERMINISTIC,
            standing=Standing.PARTIAL_ALIVE,
            general_llm_required=True,
            deterministic_candidate_ref=admission.candidate_ref,
            residual_work_ratio=residual_work.ratio,
            reason="RESIDUAL_WORK_ABOVE_RETIREMENT_THRESHOLD",
        )

    return RetirementDecision(
        disposition=RetirementDisposition.RETIRE_GENERAL_LLM,
        standing=Standing.ALIVE,
        general_llm_required=False,
        deterministic_candidate_ref=admission.candidate_ref,
        residual_work_ratio=residual_work.ratio,
        reason="EXACT_RECURRING_PATH_COMPILED_OUT",
    )


def retirement_receipt(
    recipe: CompiledRecipe,
    decision: RetirementDecision,
    observation: CompileOutObservation,
    *,
    information_sufficient: bool,
) -> RetirementReceipt:
    """Mint a deterministic receipt without carrying execution authority."""
    payload = {
        "recipe_digest": recipe.recipe_digest,
        "source_receipt_refs": recipe.source_receipt_refs,
        "cold_receipt_ref": observation.cold_receipt_ref,
        "hot_receipt_ref": observation.hot_receipt_ref,
        "information_sufficient": information_sufficient,
        "residual_work_ratio": decision.residual_work_ratio,
        "decision": decision.model_dump(mode="json"),
    }
    return RetirementReceipt(
        recipe_digest=recipe.recipe_digest,
        source_receipt_refs=recipe.source_receipt_refs,
        cold_receipt_ref=observation.cold_receipt_ref,
        hot_receipt_ref=observation.hot_receipt_ref,
        information_sufficient=information_sufficient,
        residual_work_ratio=decision.residual_work_ratio,
        decision=decision,
        receipt_digest=digest(payload),
    )


class RetirementEvaluation(FrozenModel):
    """One complete compile-out/retirement evaluation for an exact equivalence class."""

    compilation_candidate: CompilationCandidate
    recipe: CompiledRecipe | None = None
    admission: RecipeAdmission | None = None
    decision: RetirementDecision
    receipt: RetirementReceipt | None = None


class RetirementPortfolio(FrozenModel):
    """Aggregate observed retirement state without forecasting future token savings."""

    evaluations: tuple[RetirementEvaluation, ...]
    portfolio_receipt_digest: str

    @property
    def class_count(self) -> int:
        return len(self.evaluations)

    @property
    def retired_class_count(self) -> int:
        return sum(
            evaluation.decision.disposition is RetirementDisposition.RETIRE_GENERAL_LLM
            for evaluation in self.evaluations
        )

    @property
    def shadow_class_count(self) -> int:
        return sum(
            evaluation.decision.disposition is RetirementDisposition.SHADOW_DETERMINISTIC
            for evaluation in self.evaluations
        )

    @property
    def retained_class_count(self) -> int:
        return sum(
            evaluation.decision.disposition is RetirementDisposition.RETAIN_GENERAL_LLM
            for evaluation in self.evaluations
        )

    @property
    def historical_model_tokens_observed(self) -> int:
        """Tokens actually observed in the source histories; not a future-savings claim."""
        return sum(
            evaluation.compilation_candidate.model_tokens
            for evaluation in self.evaluations
        )

    @property
    def retired_history_model_tokens_observed(self) -> int:
        return sum(
            evaluation.compilation_candidate.model_tokens
            for evaluation in self.evaluations
            if evaluation.decision.disposition
            is RetirementDisposition.RETIRE_GENERAL_LLM
        )


def evaluate_recurring_class(
    episodes: tuple[CognitionEpisode, ...],
    recipe_identity: RecipeIdentity,
    current_identity: RecipeIdentity,
    *,
    candidate_ref: str,
    observation: CompileOutObservation,
    residual_work: ResidualWorkProfile,
    information_sufficient: bool,
    max_residual_work_ratio: float,
    minimum_repetitions: int = 2,
    minimum_source_receipts: int = 2,
) -> RetirementEvaluation:
    """Compose recurrence detection through retirement receipt manufacture.

    A non-recurring class returns a RETAIN decision and manufactures no recipe
    or retirement receipt. That distinction prevents a failed compilation
    precondition from being reported as a compiled artifact.
    """
    candidate = detect_compilation_candidate(
        episodes,
        minimum_repetitions=minimum_repetitions,
    )
    expected_key = (
        recipe_identity.problem_identity,
        recipe_identity.environment_identity,
        recipe_identity.authority_class,
    )
    if candidate.equivalence_key != expected_key:
        raise ValueError("COMPILATION_CANDIDATE_IDENTITY_MISMATCH")

    if not candidate.candidate:
        decision = RetirementDecision(
            disposition=RetirementDisposition.RETAIN_GENERAL_LLM,
            standing=Standing.UNKNOWN,
            general_llm_required=True,
            residual_work_ratio=residual_work.ratio,
            reason=candidate.reason,
        )
        return RetirementEvaluation(
            compilation_candidate=candidate,
            decision=decision,
        )

    recipe = compile_recipe(
        recipe_identity,
        candidate_ref=candidate_ref,
        source_receipt_refs=candidate.receipt_refs,
    )
    admission = admit_compiled_recipe(recipe, current_identity)
    decision = evaluate_retirement(
        recipe,
        admission,
        observation,
        residual_work,
        information_sufficient=information_sufficient,
        max_residual_work_ratio=max_residual_work_ratio,
        minimum_source_receipts=minimum_source_receipts,
    )
    receipt = retirement_receipt(
        recipe,
        decision,
        observation,
        information_sufficient=information_sufficient,
    )
    return RetirementEvaluation(
        compilation_candidate=candidate,
        recipe=recipe,
        admission=admission,
        decision=decision,
        receipt=receipt,
    )


def retirement_portfolio(
    evaluations: tuple[RetirementEvaluation, ...],
) -> RetirementPortfolio:
    """Content-address a finite set of exact-class retirement evaluations."""
    if not evaluations:
        raise ValueError("RETIREMENT_PORTFOLIO_REQUIRES_EVALUATIONS")
    payload = [
        {
            "equivalence_key": evaluation.compilation_candidate.equivalence_key,
            "candidate": evaluation.compilation_candidate.candidate,
            "model_tokens": evaluation.compilation_candidate.model_tokens,
            "decision": evaluation.decision.model_dump(mode="json"),
            "receipt_digest": (
                evaluation.receipt.receipt_digest
                if evaluation.receipt is not None
                else None
            ),
        }
        for evaluation in evaluations
    ]
    return RetirementPortfolio(
        evaluations=evaluations,
        portfolio_receipt_digest=digest(payload),
    )
