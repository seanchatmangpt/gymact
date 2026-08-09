"""MAPE-K autonomic consequence controller over the BRCE-exclusive DO boundary.

The controller assembles existing GymAct constitutional primitives. It never calls a
raw production actuation port and it never self-authorizes: a separately supplied
GrantIssuer must issue the identity-bound ExecutionGrant consumed by BRCE.
"""

from __future__ import annotations

from collections.abc import Collection
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import Field, model_validator

from gymact.action_contract import (
    ActionDefinition,
    AuthorityRequirement,
    ExecutionGrant,
    ExpectedEffect,
    IdempotencyClass,
    PreparedAction,
    ReversalClass,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
    construct_prepared_action,
)
from gymact.brce import BRCEBroker, BrokerRequest
from gymact.evidence import digest
from gymact.models import Capability, Consequence, FrozenModel, MaterializationResult, Standing
from gymact.runtime import ProductionGymAct


class AutonomicPhase(StrEnum):
    MONITOR = "MONITOR"
    ANALYZE = "ANALYZE"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    KNOWLEDGE = "KNOWLEDGE"


class FailureClass(StrEnum):
    NONE = "NONE"
    CONFIGURATION = "CONFIGURATION"
    AUTHORITY = "AUTHORITY"
    DEPENDENCY = "DEPENDENCY"
    CAPABILITY = "CAPABILITY"
    EXECUTION = "EXECUTION"
    VERIFICATION = "VERIFICATION"
    UNCERTAIN = "UNCERTAIN"


class AutonomicPhaseRecord(FrozenModel):
    phase: AutonomicPhase
    standing: Standing
    reason: str
    evidence_refs: tuple[str, ...] = ()


class AutonomicKnowledge(FrozenModel):
    failure_class: FailureClass
    pre_state_digest: str | None = None
    post_state_digest: str | None = None
    verification_ref: str | None = None
    verified: bool = False
    world_changed: bool | None = None
    evidence_refs: tuple[str, ...] = ()


class GrantIssue(FrozenModel):
    standing: Standing
    grant: ExecutionGrant | None = None
    reason: str

    @model_validator(mode="after")
    def admitted_issue_requires_grant(self) -> "GrantIssue":
        if self.standing is Standing.ALIVE and self.grant is None:
            raise ValueError("ALIVE_GRANT_ISSUE_REQUIRES_GRANT")
        return self


@runtime_checkable
class GrantIssuer(Protocol):
    """External policy authority that may mint a BRCE-consumable execution grant."""

    async def issue(
        self,
        *,
        action: ActionDefinition,
        prepared: PreparedAction,
        admitted_observation_ref: str,
        authority_ref: str | None,
    ) -> GrantIssue: ...


class BoundedGrantIssuer:
    """Explicit exact-ref issuer for isolated/local automation and tests.

    This issuer is never installed by default. Production callers should inject their
    real authority/policy decision point. Its purpose is to make bounded local gyms
    autonomic without weakening the same identity and scope checks used in production.
    """

    def __init__(
        self,
        allowed_authority_refs: Collection[str],
        *,
        principal: str = "urn:gymact:principal:autonomic-local",
        policy_revision: str = "local-bounded-v1",
    ) -> None:
        self._allowed = frozenset(allowed_authority_refs)
        self._principal = principal
        self._policy_revision = policy_revision

    async def issue(
        self,
        *,
        action: ActionDefinition,
        prepared: PreparedAction,
        admitted_observation_ref: str,
        authority_ref: str | None,
    ) -> GrantIssue:
        if authority_ref is None or authority_ref not in self._allowed:
            return GrantIssue(
                standing=Standing.REFUSED,
                reason="AUTHORITY_NOT_ADMITTED",
            )
        grant = ExecutionGrant(
            principal=self._principal,
            action_ref=action.semantic_id,
            subject=prepared.subject,
            capability_ref=action.capability_ref,
            authority_ref=authority_ref,
            policy_revision=self._policy_revision,
            admitted_observation_ref=admitted_observation_ref,
            intended_effects=action.expected_effects,
            scope_refs=(prepared.subject.semantic_id, prepared.subject.provider_ref),
            nonce=prepared.idempotency_key,
        )
        return GrantIssue(standing=Standing.ALIVE, grant=grant, reason="GRANT_ISSUED")


class ConsequenceRequest(FrozenModel):
    """One bounded autonomic attempt against one provider world."""

    request_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    scenario: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    capability_ref: str | None = None
    capability_binding: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    authority_ref: str | None = None
    subject_revision: str | None = None
    action_ref: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    idempotency_key: str = Field(min_length=1)
    require_verification: bool = True

    @model_validator(mode="after")
    def require_unambiguous_capability_and_verification(self) -> "ConsequenceRequest":
        if self.capability_ref is not None and self.capability_binding is not None:
            raise ValueError("CAPABILITY_SELECTOR_MUST_USE_REF_OR_BINDING_NOT_BOTH")
        if self.require_verification and not self.expected:
            raise ValueError("VERIFIED_AUTONOMIC_EXECUTION_REQUIRES_EXPECTED_STATE")
        return self


class AutonomicOutcome(FrozenModel):
    request_id: str
    provider: str
    standing: Standing
    episode_id: str | None = None
    capability_ref: str | None = None
    reason: str
    verified: bool = False
    cleanup_standing: Standing | None = None
    phase_records: tuple[AutonomicPhaseRecord, ...]
    knowledge: AutonomicKnowledge
    receipt_ids: tuple[str, ...] = ()


class AutonomicController:
    """Bounded MAPE-K controller whose EXECUTE step is BRCE-exclusive."""

    def __init__(
        self,
        runtime: ProductionGymAct,
        *,
        grant_issuer: GrantIssuer | None = None,
    ) -> None:
        if not isinstance(runtime, ProductionGymAct):
            raise TypeError("AutonomicController requires ProductionGymAct")
        self.runtime = runtime
        self.broker = BRCEBroker(runtime)
        self.grant_issuer = grant_issuer

    @staticmethod
    def _select_capability(
        capabilities: tuple[Capability, ...], request: ConsequenceRequest
    ) -> tuple[Capability | None, Standing, str]:
        do_capabilities = tuple(
            capability for capability in capabilities if capability.consequence is Consequence.DO
        )
        if request.capability_ref is not None:
            matches = tuple(
                capability
                for capability in do_capabilities
                if capability.iri == request.capability_ref
            )
        elif request.capability_binding is not None:
            matches = tuple(
                capability
                for capability in do_capabilities
                if capability.binding == request.capability_binding
            )
        else:
            matches = do_capabilities
        if not matches:
            return None, Standing.UNSUPPORTED, "NO_MATCHING_DO_CAPABILITY"
        if len(matches) != 1:
            return None, Standing.REQUIRES_CONFIGURATION, "AMBIGUOUS_DO_CAPABILITY"
        return matches[0], Standing.STRUCTURAL, "CAPABILITY_SELECTED"

    @staticmethod
    def _failure_class(standing: Standing, reason: str) -> FailureClass:
        if standing is Standing.ALIVE:
            return FailureClass.NONE
        if standing is Standing.UNCERTAIN:
            return FailureClass.UNCERTAIN
        upper = reason.upper()
        if "AUTHORITY" in upper or "GRANT" in upper or "POLICY" in upper:
            return FailureClass.AUTHORITY
        if "CONFIG" in upper or "AMBIGUOUS" in upper:
            return FailureClass.CONFIGURATION
        if "CAPABILITY" in upper or "UNSUPPORTED" in upper:
            return FailureClass.CAPABILITY
        if "VERIFY" in upper or "POSTCONDITION" in upper:
            return FailureClass.VERIFICATION
        if "MISSING" in upper or "UNAVAILABLE" in upper or "DEPEND" in upper:
            return FailureClass.DEPENDENCY
        return FailureClass.EXECUTION

    async def _finish(
        self,
        *,
        request: ConsequenceRequest,
        standing: Standing,
        reason: str,
        records: list[AutonomicPhaseRecord],
        materialization: MaterializationResult | None,
        capability_ref: str | None = None,
        verified: bool = False,
        pre_state_digest: str | None = None,
        post_state_digest: str | None = None,
        verification_ref: str | None = None,
        world_changed: bool | None = None,
    ) -> AutonomicOutcome:
        episode_id = (
            materialization.episode.episode_id
            if materialization is not None and materialization.episode is not None
            else None
        )
        cleanup_standing: Standing | None = None
        if episode_id is not None:
            try:
                cleanup = await self.runtime.teardown(
                    episode_id,
                    authority_ref=request.authority_ref,
                )
                cleanup_standing = cleanup.standing
            except Exception:
                cleanup_standing = Standing.BLOCKED
        receipts = self.runtime.episode_receipts(episode_id) if episode_id is not None else []
        evidence_refs = tuple(receipt.receipt_id for receipt in receipts)
        knowledge = AutonomicKnowledge(
            failure_class=self._failure_class(standing, reason),
            pre_state_digest=pre_state_digest,
            post_state_digest=post_state_digest,
            verification_ref=verification_ref,
            verified=verified,
            world_changed=world_changed,
            evidence_refs=evidence_refs,
        )
        return AutonomicOutcome(
            request_id=request.request_id,
            provider=request.provider,
            standing=standing,
            episode_id=episode_id,
            capability_ref=capability_ref,
            reason=reason,
            verified=verified,
            cleanup_standing=cleanup_standing,
            phase_records=tuple(records),
            knowledge=knowledge,
            receipt_ids=evidence_refs,
        )

    async def run(self, request: ConsequenceRequest) -> AutonomicOutcome:
        records: list[AutonomicPhaseRecord] = []
        materialization = await self.runtime.create_episode(
            request.provider,
            scenario=request.scenario,
            config=request.config,
            authority_ref=request.authority_ref,
            idempotency_key=f"{request.idempotency_key}:materialize",
        )
        records.append(
            AutonomicPhaseRecord(
                phase=AutonomicPhase.MONITOR,
                standing=materialization.standing,
                reason=materialization.receipt.reason or "WORLD_MATERIALIZED",
                evidence_refs=(materialization.receipt.receipt_id,),
            )
        )
        if not materialization.accepted or materialization.episode is None:
            return await self._finish(
                request=request,
                standing=materialization.standing,
                reason=materialization.receipt.reason or "MATERIALIZATION_NOT_ACCEPTED",
                records=records,
                materialization=materialization,
            )

        episode = materialization.episode
        initial = materialization.observation or await self.runtime.observe(episode.episode_id)
        capability, analysis_standing, analysis_reason = self._select_capability(
            self.runtime.capabilities(episode.episode_id), request
        )
        records.append(
            AutonomicPhaseRecord(
                phase=AutonomicPhase.ANALYZE,
                standing=analysis_standing,
                reason=analysis_reason,
                evidence_refs=(materialization.receipt.receipt_id,),
            )
        )
        if capability is None:
            return await self._finish(
                request=request,
                standing=analysis_standing,
                reason=analysis_reason,
                records=records,
                materialization=materialization,
                pre_state_digest=initial.state_digest,
                post_state_digest=initial.state_digest,
                world_changed=False,
            )

        subject = SubjectRef(
            semantic_id=episode.environment_id,
            provider_ref=request.provider,
            revision=request.subject_revision,
        )
        expected_effect = ExpectedEffect(
            predicate="urn:gymact:predicate:partial-state-equals",
            parameters=request.expected,
        )
        action = ActionDefinition(
            semantic_id=request.action_ref
            or f"urn:gymact:autonomic-action:{request.provider}:{capability.binding}",
            provider_ref=request.provider,
            capability_ref=capability.iri,
            subject_type="urn:gymact:Environment",
            input_schema=request.input_schema,
            expected_effects=(expected_effect,),
            authority=AuthorityRequirement(capability_refs=(capability.iri,)),
            verification=VerificationStrategy(
                kind=VerificationKind.EXACT_STATE,
                observer_ref="urn:gymact:observer:environment-verify",
                expected=request.expected,
            ),
            idempotency=IdempotencyClass.CONDITIONALLY_IDEMPOTENT,
            idempotency_fields=("idempotency_key",),
            reversal=ReversalClass.UNKNOWN,
            standing=Standing.STRUCTURAL,
        )
        prepared = construct_prepared_action(
            action,
            episode_id=episode.episode_id,
            subject=subject,
            payload=request.payload,
            admission_digest=digest(
                {
                    "request_id": request.request_id,
                    "observation": initial.state_digest,
                    "action": action.semantic_id,
                    "payload": request.payload,
                }
            ),
            idempotency_key=request.idempotency_key,
        )
        if self.grant_issuer is None:
            records.append(
                AutonomicPhaseRecord(
                    phase=AutonomicPhase.PLAN,
                    standing=Standing.REFUSED,
                    reason="EXECUTION_GRANT_ISSUER_REQUIRED",
                )
            )
            return await self._finish(
                request=request,
                standing=Standing.REFUSED,
                reason="EXECUTION_GRANT_ISSUER_REQUIRED",
                records=records,
                materialization=materialization,
                capability_ref=capability.iri,
                pre_state_digest=initial.state_digest,
                post_state_digest=initial.state_digest,
                world_changed=False,
            )

        grant_issue = await self.grant_issuer.issue(
            action=action,
            prepared=prepared,
            admitted_observation_ref=f"urn:gymact:observation:{initial.state_digest}",
            authority_ref=request.authority_ref,
        )
        records.append(
            AutonomicPhaseRecord(
                phase=AutonomicPhase.PLAN,
                standing=grant_issue.standing,
                reason=grant_issue.reason,
            )
        )
        if grant_issue.standing is not Standing.ALIVE or grant_issue.grant is None:
            return await self._finish(
                request=request,
                standing=grant_issue.standing,
                reason=grant_issue.reason,
                records=records,
                materialization=materialization,
                capability_ref=capability.iri,
                pre_state_digest=initial.state_digest,
                post_state_digest=initial.state_digest,
                world_changed=False,
            )

        transition = await self.broker.execute(
            BrokerRequest(
                action=action,
                prepared=prepared,
                grant=grant_issue.grant,
                current_revision=request.subject_revision,
                expected=request.expected,
            )
        )
        execute_reason = transition.receipt.reason or "BRCE_EXECUTION_COMPLETED"
        records.append(
            AutonomicPhaseRecord(
                phase=AutonomicPhase.EXECUTE,
                standing=transition.standing,
                reason=execute_reason,
                evidence_refs=(transition.receipt.receipt_id,),
            )
        )
        verification = transition.verification
        verified = bool(verification is not None and verification.passed)
        knowledge_reason = (
            "VERIFIED_CONSEQUENCE_ADMITTED"
            if transition.standing is Standing.ALIVE and verified
            else execute_reason
        )
        records.append(
            AutonomicPhaseRecord(
                phase=AutonomicPhase.KNOWLEDGE,
                standing=transition.standing,
                reason=knowledge_reason,
                evidence_refs=(transition.receipt.receipt_id,),
            )
        )
        post_digest = (
            verification.state_digest
            if verification is not None
            else (
                transition.actuation.observation.state_digest
                if transition.actuation.observation is not None
                else initial.state_digest
            )
        )
        return await self._finish(
            request=request,
            standing=transition.standing,
            reason=knowledge_reason,
            records=records,
            materialization=materialization,
            capability_ref=capability.iri,
            verified=verified,
            pre_state_digest=initial.state_digest,
            post_state_digest=post_digest,
            verification_ref=verification.verification_id if verification is not None else None,
            world_changed=transition.receipt.world_changed,
        )
