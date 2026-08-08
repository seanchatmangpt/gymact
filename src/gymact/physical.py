"""Safety-first structural contracts for robotics, industrial/OT, and edge controllers."""
from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from gymact.models import FrozenModel, Standing


class PhysicalDomain(StrEnum):
    ROBOTICS = "robotics"
    INDUSTRIAL_OT = "industrial_ot"


class RiskClass(StrEnum):
    READ_ONLY = "READ_ONLY"
    REVERSIBLE = "REVERSIBLE"
    CONSEQUENTIAL = "CONSEQUENTIAL"
    IRREVERSIBLE = "IRREVERSIBLE"


class ControllerMode(StrEnum):
    WASM = "wasm"
    NATIVE = "native"


class SafetyEnvelope(FrozenModel):
    domain: PhysicalDomain
    allowed_operations: tuple[str, ...]
    policy_refs: tuple[str, ...]
    emergency_stop_ref: str = Field(min_length=1)
    physical_verifier_ref: str = Field(min_length=1)
    safe_state_ref: str = Field(min_length=1)
    max_duration_s: float = Field(gt=0.0)
    max_rate_hz: float = Field(gt=0.0)
    require_human_approval_for_irreversible: bool = True
    autonomous_policy_stricter_than_user: bool = True

    @model_validator(mode="after")
    def require_bounded_operations(self) -> Self:
        if not self.allowed_operations:
            raise ValueError("PHYSICAL_EFFECTOR_REQUIRES_ALLOWLIST")
        if not self.policy_refs:
            raise ValueError("PHYSICAL_EFFECTOR_REQUIRES_POLICY")
        return self


class PhysicalCommand(FrozenModel):
    domain: PhysicalDomain
    operation: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    requested_duration_s: float = Field(gt=0.0)
    risk: RiskClass
    expected_effect_ref: str = Field(min_length=1)
    authority_ref: str | None = None
    human_approval_ref: str | None = None


class PhysicalAdmission(FrozenModel):
    admitted: bool
    standing: Standing
    reason: str


def admit_physical_command(
    envelope: SafetyEnvelope,
    command: PhysicalCommand,
) -> PhysicalAdmission:
    """Admit a candidate physical command. This function has no actuator handle."""
    if command.domain is not envelope.domain:
        return PhysicalAdmission(
            admitted=False, standing=Standing.REFUSED, reason="DOMAIN_REFUSED"
        )
    if command.operation not in envelope.allowed_operations:
        return PhysicalAdmission(
            admitted=False, standing=Standing.REFUSED, reason="CAPABILITY_REFUSED"
        )
    if command.requested_duration_s > envelope.max_duration_s:
        return PhysicalAdmission(
            admitted=False, standing=Standing.REFUSED, reason="SAFETY_BOUND_REFUSED"
        )
    if not command.authority_ref:
        return PhysicalAdmission(
            admitted=False, standing=Standing.REFUSED, reason="AUTHORITY_REFUSED"
        )
    if (
        command.risk is RiskClass.IRREVERSIBLE
        and envelope.require_human_approval_for_irreversible
        and not command.human_approval_ref
    ):
        return PhysicalAdmission(
            admitted=False, standing=Standing.REFUSED, reason="HUMAN_APPROVAL_REQUIRED"
        )
    return PhysicalAdmission(
        admitted=True,
        standing=Standing.CANDIDATE,
        reason="PHYSICAL_CANDIDATE_ADMITTED_BRCE_STILL_REQUIRED",
    )


class PhysicalProviderProfile(FrozenModel):
    provider_ref: str = Field(min_length=1)
    domain: PhysicalDomain
    driver_protocol: str = Field(min_length=1)
    safety_envelope_ref: str = Field(min_length=1)
    standing: Standing = Standing.STRUCTURAL
    live_subject_evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def alive_requires_live_subject_evidence(self) -> Self:
        if self.standing is Standing.ALIVE and not self.live_subject_evidence_refs:
            raise ValueError("PHYSICAL_PROVIDER_ALIVE_REQUIRES_REAL_SUBJECT_EVIDENCE")
        return self


class EdgeControllerArtifact(FrozenModel):
    controller_id: str = Field(min_length=1)
    action_refs: tuple[str, ...]
    authority_policy_refs: tuple[str, ...]
    verifier_refs: tuple[str, ...]
    safe_state_ref: str = Field(min_length=1)
    execution_mode: ControllerMode
    content_digest: str = Field(min_length=1)
    causal_site: str = Field(min_length=1)
    standing: Standing = Standing.STRUCTURAL

    @model_validator(mode="after")
    def require_control_closure(self) -> Self:
        if not self.action_refs:
            raise ValueError("EDGE_CONTROLLER_REQUIRES_ACTIONS")
        if not self.authority_policy_refs:
            raise ValueError("EDGE_CONTROLLER_REQUIRES_AUTHORITY_POLICY")
        if not self.verifier_refs:
            raise ValueError("EDGE_CONTROLLER_REQUIRES_VERIFIER")
        if self.standing is Standing.ALIVE:
            raise ValueError("EDGE_CONTROLLER_ALIVE_REQUIRES_EXECUTION_RECEIPT_NOT_MANIFEST")
        return self
