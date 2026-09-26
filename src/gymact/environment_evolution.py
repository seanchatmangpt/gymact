"""Generator-neutral environment evolution admission for bounded GymAct worlds.

The evolution generator is deliberately outside the trusted core. It may be an LLM,
planner, search procedure, mutation system, procedural graph, or a human-authored seed.
GymAct admits only the resulting candidate against exact environment, task, evidence,
history, evaluator, and validation identities.

This module does not execute consequential DO. It qualifies a powerless evolution
candidate and manufactures the next bounded seed identity. Materializing that seed still
uses GymAct's existing authority/BRCE path and receives its own runtime receipts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from blake3 import blake3
from pydantic import Field, model_validator

from gymact.evidence import digest
from gymact.models import FrozenModel, Standing

_CONTENT_DIGEST = r"^(?:sha256|blake3):[0-9a-f]{64}$"
_GIT_SHA = r"^[0-9a-f]{40}$"


def task_request_digest(value: str) -> str:
    """Return byte identity for the exact UTF-8 task request."""

    return "blake3:" + blake3(value.encode("utf-8")).hexdigest()


class EvolutionDecisionKind(StrEnum):
    """Counter-default decision families from the environment-evolution protocol."""

    TEMPORAL = "temporal"
    EXCLUSION = "exclusion"
    EXCEPTION_RULE = "exception_rule"
    NUMERICAL = "numerical"


class EvolutionEventOperation(StrEnum):
    """File/state operations carried by a causal evolution-history fragment."""

    CREATE = "create"
    MODIFY = "modify"
    RENAME = "rename"
    DELETE = "delete"


class EvolutionEcosystemBinding(FrozenModel):
    """Exact ecosystem provenance for one powerless evolution candidate."""

    marketplace_repository: Literal["seanchatmangpt/ggen-marketplace"] = (
        "seanchatmangpt/ggen-marketplace"
    )
    marketplace_commit_sha: str = Field(pattern=_GIT_SHA)
    marketplace_pack: Literal["environment-evolution-pack"] = "environment-evolution-pack"
    marketplace_pack_version: Literal["26.9.25"] = "26.9.25"
    autofde_selection_digest: str = Field(pattern=_CONTENT_DIGEST)
    sjira_work_order_id: str = Field(min_length=1)
    sjira_base_sha: str = Field(pattern=_GIT_SHA)
    sa2a_candidate_digest: str = Field(pattern=_CONTENT_DIGEST)


class EvolutionDecisionPoint(FrozenModel):
    """One plausible wrong choice plus evidence and a check that resolves it."""

    decision_id: str = Field(min_length=1)
    kind: EvolutionDecisionKind
    plausible_wrong_choice: str
    resolving_evidence_refs: tuple[str, ...] = ()
    rejecting_check_ref: str
    evidence_chain_length: int = Field(ge=0)


class EvolutionEvent(FrozenModel):
    """One causal operation in the generated environment history."""

    event_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    operation: EvolutionEventOperation
    target_ref: str = Field(min_length=1)
    consequence_digest: str = Field(pattern=_CONTENT_DIGEST)
    depends_on_event_ids: tuple[str, ...] = ()


class EvolutionSeed(FrozenModel):
    """Exact bounded environment state from which the next variant may be proposed."""

    seed_id: str = Field(min_length=1)
    generation: int = Field(ge=0)
    environment_digest: str = Field(pattern=_CONTENT_DIGEST)
    task_request: str
    task_request_digest: str = Field(pattern=_CONTENT_DIGEST)
    reference_outcome_digest: str = Field(pattern=_CONTENT_DIGEST)
    evaluator_digest: str = Field(pattern=_CONTENT_DIGEST)
    history_digest: str = Field(pattern=_CONTENT_DIGEST)
    history_event_ids: tuple[str, ...] = ()
    last_event_sequence: int = Field(ge=-1)
    min_evidence_chain_length: int = Field(ge=1, default=1)
    source_candidate_digest: str | None = Field(default=None, pattern=_CONTENT_DIGEST)

    @model_validator(mode="after")
    def bind_task_bytes(self) -> Self:
        if self.task_request_digest != task_request_digest(self.task_request):
            raise ValueError("EVOLUTION_SEED_TASK_DIGEST_MISMATCH")
        if self.history_event_ids and self.last_event_sequence < len(self.history_event_ids) - 1:
            raise ValueError("EVOLUTION_SEED_HISTORY_SEQUENCE_INCONSISTENT")
        return self

    @property
    def seed_digest(self) -> str:
        return "blake3:" + digest(self.model_dump(mode="json"))


class EvolutionCandidate(FrozenModel):
    """Powerless proposed transition from one exact environment state to the next."""

    candidate_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    parent_environment_digest: str = Field(pattern=_CONTENT_DIGEST)
    parent_history_digest: str = Field(pattern=_CONTENT_DIGEST)
    task_request: str
    task_request_digest: str = Field(pattern=_CONTENT_DIGEST)
    direction: str = Field(min_length=1)
    generator_ref: str = Field(min_length=1)
    ecosystem: EvolutionEcosystemBinding
    new_environment_digest: str = Field(pattern=_CONTENT_DIGEST)
    reference_outcome_digest: str = Field(pattern=_CONTENT_DIGEST)
    evaluator_digest: str = Field(pattern=_CONTENT_DIGEST)
    decision_points: tuple[EvolutionDecisionPoint, ...] = ()
    events: tuple[EvolutionEvent, ...] = ()
    failure_feedback_digests: tuple[str, ...] = ()
    authority_ceiling: Literal["OBSERVE|SELECT|CONSTRUCT"] = "OBSERVE|SELECT|CONSTRUCT"
    grants_do_authority: Literal[False] = False

    @model_validator(mode="after")
    def bind_task_bytes_and_feedback(self) -> Self:
        if self.task_request_digest != task_request_digest(self.task_request):
            raise ValueError("EVOLUTION_CANDIDATE_TASK_DIGEST_MISMATCH")
        for feedback_digest in self.failure_feedback_digests:
            if not (
                feedback_digest.startswith("sha256:")
                or feedback_digest.startswith("blake3:")
            ):
                raise ValueError("EVOLUTION_FAILURE_FEEDBACK_DIGEST_INVALID")
            if len(feedback_digest.split(":", 1)[1]) != 64:
                raise ValueError("EVOLUTION_FAILURE_FEEDBACK_DIGEST_INVALID")
        return self

    @property
    def candidate_digest(self) -> str:
        return "blake3:" + digest(self.model_dump(mode="json"))

    @property
    def event_history_digest(self) -> str:
        return "blake3:" + digest(
            {
                "parent_history_digest": self.parent_history_digest,
                "events": [event.model_dump(mode="json") for event in self.events],
            }
        )


class EvolutionValidation(FrozenModel):
    """Independent observations over a materialized candidate environment."""

    observer_ref: str = Field(min_length=1)
    evidence_digest: str = Field(pattern=_CONTENT_DIGEST)
    observed_parent_environment_digest: str = Field(pattern=_CONTENT_DIGEST)
    observed_task_request_digest: str = Field(pattern=_CONTENT_DIGEST)
    observed_environment_digest: str = Field(pattern=_CONTENT_DIGEST)
    structural_checks_passed: bool
    history_checks_passed: bool
    material_placement_checks_passed: bool
    evaluation_asset_syntax_passed: bool
    shortcut_audit_passed: bool
    new_reference_passed: bool
    previous_reference_failed: bool
    decision_point_checks_passed: bool


class EvolutionAdmission(FrozenModel):
    """Construct-only court result; it is not a GymAct DO receipt."""

    seed_digest: str = Field(pattern=_CONTENT_DIGEST)
    candidate_digest: str = Field(pattern=_CONTENT_DIGEST)
    validation_evidence_digest: str = Field(pattern=_CONTENT_DIGEST)
    admitted: bool
    standing: Standing
    reasons: tuple[str, ...]
    authority: Literal["none"] = "none"


class EvolutionTransition(FrozenModel):
    """One admitted recursive step with a next-seed identity and no ambient authority."""

    admission: EvolutionAdmission
    previous_seed_digest: str = Field(pattern=_CONTENT_DIGEST)
    candidate_digest: str = Field(pattern=_CONTENT_DIGEST)
    next_seed: EvolutionSeed
    authority: Literal["none"] = "none"


class EnvironmentEvolutionCourt:
    """Admit generator-neutral environment variants and manufacture the next seed."""

    def qualify(
        self,
        seed: EvolutionSeed,
        candidate: EvolutionCandidate,
        validation: EvolutionValidation,
    ) -> EvolutionAdmission:
        reasons: list[str] = []

        if candidate.generation != seed.generation + 1:
            reasons.append("GENERATION_DISCONTINUITY")
        if candidate.parent_environment_digest != seed.environment_digest:
            reasons.append("PARENT_ENVIRONMENT_MISMATCH")
        if candidate.parent_history_digest != seed.history_digest:
            reasons.append("PARENT_HISTORY_MISMATCH")
        if candidate.task_request != seed.task_request:
            reasons.append("TASK_REQUEST_CHANGED")
        if candidate.task_request_digest != seed.task_request_digest:
            reasons.append("TASK_REQUEST_DIGEST_CHANGED")
        if candidate.new_environment_digest == seed.environment_digest:
            reasons.append("ENVIRONMENT_UNCHANGED")
        if candidate.reference_outcome_digest == seed.reference_outcome_digest:
            reasons.append("REFERENCE_OUTCOME_UNCHANGED")
        if candidate.evaluator_digest == seed.evaluator_digest:
            reasons.append("EVALUATOR_UNCHANGED")

        if len(candidate.decision_points) < 3:
            reasons.append("INSUFFICIENT_DECISION_POINTS")
        decision_ids = [point.decision_id for point in candidate.decision_points]
        if len(decision_ids) != len(set(decision_ids)):
            reasons.append("DUPLICATE_DECISION_POINT_ID")
        for point in candidate.decision_points:
            if not point.plausible_wrong_choice.strip():
                reasons.append(f"WRONG_CHOICE_MISSING:{point.decision_id}")
            if not point.resolving_evidence_refs:
                reasons.append(f"RESOLVING_EVIDENCE_MISSING:{point.decision_id}")
            if not point.rejecting_check_ref.strip():
                reasons.append(f"REJECTING_CHECK_MISSING:{point.decision_id}")
            if point.evidence_chain_length < seed.min_evidence_chain_length:
                reasons.append(f"EVIDENCE_CHAIN_REGRESSION:{point.decision_id}")

        if not candidate.events:
            reasons.append("EVOLUTION_EVENT_REQUIRED")
        event_ids = [event.event_id for event in candidate.events]
        if len(event_ids) != len(set(event_ids)):
            reasons.append("DUPLICATE_EVOLUTION_EVENT_ID")

        first_sequence = seed.last_event_sequence + 1
        expected_sequences = list(
            range(first_sequence, first_sequence + len(candidate.events))
        )
        actual_sequences = [event.sequence for event in candidate.events]
        if actual_sequences != expected_sequences:
            reasons.append("EVOLUTION_EVENT_SEQUENCE_GAP")

        available_events = set(seed.history_event_ids)
        for event in candidate.events:
            missing = set(event.depends_on_event_ids) - available_events
            if missing:
                reasons.append(f"CAUSAL_DEPENDENCY_MISSING:{event.event_id}")
            available_events.add(event.event_id)

        if validation.observed_parent_environment_digest != seed.environment_digest:
            reasons.append("OBSERVED_PARENT_ENVIRONMENT_MISMATCH")
        if validation.observed_task_request_digest != seed.task_request_digest:
            reasons.append("OBSERVED_TASK_REQUEST_MISMATCH")
        if validation.observed_environment_digest != candidate.new_environment_digest:
            reasons.append("OBSERVED_ENVIRONMENT_MISMATCH")
        if not validation.structural_checks_passed:
            reasons.append("STRUCTURAL_VALIDATION_FAILED")
        if not validation.history_checks_passed:
            reasons.append("HISTORY_VALIDATION_FAILED")
        if not validation.material_placement_checks_passed:
            reasons.append("MATERIAL_PLACEMENT_VALIDATION_FAILED")
        if not validation.evaluation_asset_syntax_passed:
            reasons.append("EVALUATION_ASSET_SYNTAX_FAILED")
        if not validation.shortcut_audit_passed:
            reasons.append("SHORTCUT_AUDIT_FAILED")
        if not validation.new_reference_passed:
            reasons.append("NEW_REFERENCE_FAILED")
        if not validation.previous_reference_failed:
            reasons.append("PREVIOUS_REFERENCE_SURVIVED")
        if not validation.decision_point_checks_passed:
            reasons.append("DECISION_POINT_VALIDATION_FAILED")

        admitted = not reasons
        return EvolutionAdmission(
            seed_digest=seed.seed_digest,
            candidate_digest=candidate.candidate_digest,
            validation_evidence_digest=validation.evidence_digest,
            admitted=admitted,
            standing=Standing.STRUCTURAL if admitted else Standing.REFUSED,
            reasons=("EVOLUTION_COURT_CONFORMS",) if admitted else tuple(reasons),
        )

    def require_admitted(
        self,
        seed: EvolutionSeed,
        candidate: EvolutionCandidate,
        validation: EvolutionValidation,
    ) -> EvolutionAdmission:
        admission = self.qualify(seed, candidate, validation)
        if not admission.admitted:
            raise ValueError("ENVIRONMENT_EVOLUTION_REFUSED:" + ",".join(admission.reasons))
        return admission

    def advance(
        self,
        seed: EvolutionSeed,
        candidate: EvolutionCandidate,
        validation: EvolutionValidation,
    ) -> EvolutionTransition:
        """Promote an admitted variant to the next bounded seed without performing DO."""

        admission = self.require_admitted(seed, candidate, validation)
        chain_floor = min(point.evidence_chain_length for point in candidate.decision_points)
        next_seed = EvolutionSeed(
            seed_id=f"seed:{candidate.candidate_id}",
            generation=candidate.generation,
            environment_digest=candidate.new_environment_digest,
            task_request=seed.task_request,
            task_request_digest=seed.task_request_digest,
            reference_outcome_digest=candidate.reference_outcome_digest,
            evaluator_digest=candidate.evaluator_digest,
            history_digest=candidate.event_history_digest,
            history_event_ids=seed.history_event_ids
            + tuple(event.event_id for event in candidate.events),
            last_event_sequence=candidate.events[-1].sequence,
            min_evidence_chain_length=max(seed.min_evidence_chain_length, chain_floor),
            source_candidate_digest=candidate.candidate_digest,
        )
        return EvolutionTransition(
            admission=admission,
            previous_seed_digest=seed.seed_digest,
            candidate_digest=candidate.candidate_digest,
            next_seed=next_seed,
        )
