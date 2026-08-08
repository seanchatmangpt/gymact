"""Crown semantic-action contracts for consequential GymAct providers.

These models are intentionally transport-neutral. They describe candidate actions,
authority requirements, expected effects, observation/verification, retry law, cost,
and causal locality without granting execution authority.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import Field, model_validator

from gymact.models import FrozenModel, Standing


class IdempotencyClass(StrEnum):
    IDEMPOTENT = "IDEMPOTENT"
    CONDITIONALLY_IDEMPOTENT = "CONDITIONALLY_IDEMPOTENT"
    NON_IDEMPOTENT = "NON_IDEMPOTENT"
    UNKNOWN = "UNKNOWN"


class ReversalClass(StrEnum):
    REVERSIBLE = "REVERSIBLE"
    COMPENSATABLE = "COMPENSATABLE"
    IRREVERSIBLE = "IRREVERSIBLE"
    UNKNOWN = "UNKNOWN"


class ObservationConfidence(StrEnum):
    SELF_REPORTED = "SELF_REPORTED"
    SAME_PROVIDER_OBSERVED = "SAME_PROVIDER_OBSERVED"
    INDEPENDENT_CHANNEL = "INDEPENDENT_CHANNEL"
    MULTI_ORACLE = "MULTI_ORACLE"
    PHYSICAL_SENSOR = "PHYSICAL_SENSOR"


class VerificationKind(StrEnum):
    EXACT_STATE = "EXACT_STATE"
    PREDICATE = "PREDICATE"
    SHACL = "SHACL"
    QUERY = "QUERY"
    DIGEST = "DIGEST"
    RESOURCE_EXISTS = "RESOURCE_EXISTS"
    RESOURCE_ABSENT = "RESOURCE_ABSENT"
    REVISION = "REVISION"
    EVENT = "EVENT"
    PROCESS_CONFORMANCE = "PROCESS_CONFORMANCE"
    TEMPORAL_STABILIZATION = "TEMPORAL_STABILIZATION"
    QUORUM = "QUORUM"


class AcknowledgementStatus(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    LOST = "LOST"
    UNKNOWN = "UNKNOWN"


class RefusalCode(StrEnum):
    AUTHORITY_REFUSED = "AUTHORITY_REFUSED"
    IDENTITY_REFUSED = "IDENTITY_REFUSED"
    CAPABILITY_REFUSED = "CAPABILITY_REFUSED"
    PRECONDITION_REFUSED = "PRECONDITION_REFUSED"
    STALE_OBSERVATION_REFUSED = "STALE_OBSERVATION_REFUSED"
    REVISION_MISMATCH_REFUSED = "REVISION_MISMATCH_REFUSED"
    POLICY_REFUSED = "POLICY_REFUSED"
    UNSAFE_RETRY_REFUSED = "UNSAFE_RETRY_REFUSED"
    AMBIGUOUS_SUBJECT_REFUSED = "AMBIGUOUS_SUBJECT_REFUSED"
    VERIFICATION_REFUSED = "VERIFICATION_REFUSED"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    PROVIDER_CONFIGURATION_REQUIRED = "PROVIDER_CONFIGURATION_REQUIRED"


class ReconciliationDisposition(StrEnum):
    EFFECT_CONFIRMED = "EFFECT_CONFIRMED"
    NO_EFFECT = "NO_EFFECT"
    PARTIAL_EFFECT = "PARTIAL_EFFECT"
    STILL_UNCERTAIN = "STILL_UNCERTAIN"
    RETRY_ADMITTED = "RETRY_ADMITTED"
    RETRY_REFUSED = "RETRY_REFUSED"


class SubjectRef(FrozenModel):
    semantic_id: str = Field(min_length=1)
    provider_ref: str = Field(min_length=1)
    revision: str | None = None


class AuthorityRequirement(FrozenModel):
    capability_refs: tuple[str, ...] = ()
    policy_refs: tuple[str, ...] = ()
    autonomous_policy_may_be_stricter: bool = True


class ExpectedEffect(FrozenModel):
    predicate: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class VerificationStrategy(FrozenModel):
    kind: VerificationKind
    observer_ref: str = Field(min_length=1)
    expected: dict[str, Any] = Field(default_factory=dict)
    minimum_confidence: ObservationConfidence = ObservationConfidence.SAME_PROVIDER_OBSERVED
    settle_timeout_s: float = Field(default=0.0, ge=0.0)
    quorum: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def require_quorum_for_quorum_strategy(self) -> Self:
        if self.kind is VerificationKind.QUORUM and self.quorum < 2:
            raise ValueError("QUORUM_VERIFICATION_REQUIRES_AT_LEAST_TWO_ORACLES")
        return self


class CostModel(FrozenModel):
    monetary: float = Field(default=0.0, ge=0.0)
    expected_wall_time_s: float = Field(default=0.0, ge=0.0)
    compute_units: float = Field(default=0.0, ge=0.0)
    expected_human_approvals: float = Field(default=0.0, ge=0.0)
    expected_failure_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class CausalLocality(FrozenModel):
    execution_site: str = "unspecified"
    observer_site: str = "unspecified"
    estimated_hops: int | None = Field(default=None, ge=0)
    estimated_effect_latency_s: float | None = Field(default=None, ge=0.0)
    estimated_observation_latency_s: float | None = Field(default=None, ge=0.0)


class ActionDefinition(FrozenModel):
    """Machine-inspectable semantic action definition; never an execution grant."""

    semantic_id: str = Field(min_length=1)
    provider_ref: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    subject_type: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] = Field(default_factory=dict)
    preconditions: tuple[str, ...] = ()
    authority: AuthorityRequirement = Field(default_factory=AuthorityRequirement)
    expected_effects: tuple[ExpectedEffect, ...]
    verification: VerificationStrategy
    idempotency: IdempotencyClass = IdempotencyClass.UNKNOWN
    idempotency_fields: tuple[str, ...] = ()
    reversal: ReversalClass = ReversalClass.UNKNOWN
    compensation_action_ref: str | None = None
    cost: CostModel = Field(default_factory=CostModel)
    locality: CausalLocality = Field(default_factory=CausalLocality)
    standing: Standing = Standing.UNKNOWN
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def enforce_execution_semantics(self) -> Self:
        if (
            self.idempotency is IdempotencyClass.CONDITIONALLY_IDEMPOTENT
            and not self.idempotency_fields
        ):
            raise ValueError("CONDITIONAL_IDEMPOTENCY_REQUIRES_KEY_FIELDS")
        if self.reversal is ReversalClass.COMPENSATABLE and not self.compensation_action_ref:
            raise ValueError("COMPENSATABLE_ACTION_REQUIRES_COMPENSATION_ACTION_REF")
        if self.standing is Standing.ALIVE and not self.evidence_refs:
            raise ValueError("ALIVE_ACTION_REQUIRES_EXECUTION_EVIDENCE")
        if self.standing is Standing.ADOPTED and not self.evidence_refs:
            raise ValueError("ADOPTED_ACTION_REQUIRES_EXTERNAL_EVIDENCE")
        return self


class ExecutionGrant(FrozenModel):
    """Identity-bound authority token consumed by the BRCE DO boundary."""

    principal: str = Field(min_length=1)
    delegated_principal: str | None = None
    action_ref: str = Field(min_length=1)
    subject: SubjectRef
    capability_ref: str = Field(min_length=1)
    authority_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    admitted_observation_ref: str = Field(min_length=1)
    intended_effects: tuple[ExpectedEffect, ...]
    expires_at: str | None = None
    nonce: str = Field(min_length=1)


class PreparedAction(FrozenModel):
    """Constructed executable intent. Possession does not authorize DO."""

    action_ref: str = Field(min_length=1)
    subject: SubjectRef
    payload: dict[str, Any] = Field(default_factory=dict)
    admission_digest: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class ExecutionAcknowledgement(FrozenModel):
    status: AcknowledgementStatus
    provider_operation_ref: str | None = None
    provider_payload: dict[str, Any] = Field(default_factory=dict)


class UncertainExecution(FrozenModel):
    action_ref: str = Field(min_length=1)
    subject: SubjectRef
    idempotency_key: str = Field(min_length=1)
    pre_state_digest: str = Field(min_length=1)
    last_observed_state_digest: str | None = None
    acknowledgement: ExecutionAcknowledgement
    reason: str = Field(min_length=1)


class ReconciliationResult(FrozenModel):
    disposition: ReconciliationDisposition
    standing: Standing
    observed_state_digest: str | None = None
    verification_ref: str | None = None
    retry_admitted: bool = False
    reason: str | None = None

    @model_validator(mode="after")
    def retry_requires_explicit_disposition(self) -> Self:
        if self.disposition is ReconciliationDisposition.STILL_UNCERTAIN and self.retry_admitted:
            raise ValueError("UNCERTAIN_OUTCOME_CANNOT_IMPLY_RETRY")
        if (
            self.retry_admitted
            and self.disposition is not ReconciliationDisposition.RETRY_ADMITTED
        ):
            raise ValueError("RETRY_REQUIRES_RETRY_ADMITTED_DISPOSITION")
        return self


class ProviderMetadata(FrozenModel):
    semantic_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    provider_families: tuple[str, ...]
    supports_independent_observation: bool
    locality: CausalLocality = Field(default_factory=CausalLocality)


class ProviderHealth(FrozenModel):
    standing: Standing
    observed_at: str
    subject_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    reason: str | None = None
