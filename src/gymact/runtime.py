"""Small, bounded semantic runtime for executable benchmark worlds."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import anyio

from gymact.authority import AuthorityResolver, DenyAuthorityResolver
from gymact.evidence import (
    MemoryReceiptLedger,
    ReceiptLedger,
    canonical_json_bytes,
    digest_json,
    digest_text,
    receipts_to_prov,
)
from gymact.models import (
    ActuationIntent,
    ActuationResult,
    AuthorityDecision,
    AuthorityRequest,
    Capability,
    Consequence,
    Episode,
    JsonObject,
    MaterializationIntent,
    MaterializationResult,
    Observation,
    Operation,
    Receipt,
    ReceiptStage,
    RuntimeLimits,
    Standing,
    VerificationResult,
)
from gymact.providers import Environment, EnvironmentProvider
from gymact.semantic import ProfileAuthority

_PROVIDER_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,256}$")


class GymActOperationError(RuntimeError):
    """Typed non-consequential/runtime failure carrying evidence when available."""

    def __init__(self, message: str, *, receipt: Receipt | None = None) -> None:
        super().__init__(message)
        self.receipt = receipt


@dataclass
class _EpisodeState:
    episode: Episode
    environment: Environment
    lock: anyio.Lock = field(default_factory=anyio.Lock)


@dataclass(frozen=True)
class _ActuationRecord:
    intent_digest: str
    result: ActuationResult


@dataclass(frozen=True)
class _MaterializationRecord:
    intent_digest: str
    result: MaterializationResult


class GymAct:
    """Reference orchestrator with fail-closed authority and receipted consequence."""

    def __init__(
        self,
        *,
        validate_profile: bool = True,
        authority_resolver: AuthorityResolver | None = None,
        ledger: ReceiptLedger | None = None,
        limits: RuntimeLimits | None = None,
    ) -> None:
        self._providers: dict[str, EnvironmentProvider] = {}
        self._episodes: dict[str, _EpisodeState] = {}
        self._actuation_idempotency: dict[tuple[str, str], _ActuationRecord] = {}
        self._materialization_idempotency: dict[str, _MaterializationRecord] = {}
        self._materialization_lock = anyio.Lock()
        self._teardown_receipts: dict[str, Receipt] = {}
        self._authority = authority_resolver or DenyAuthorityResolver()
        self._ledger = ledger or MemoryReceiptLedger()
        self.limits = limits or RuntimeLimits()
        self.profile = ProfileAuthority()
        if validate_profile:
            result = self.profile.validate()
            if not result.conforms:
                raise RuntimeError(f"GymAct semantic profile invalid: {result.report_text}")

    @property
    def ledger(self) -> ReceiptLedger:
        """Return the configured append-only evidence ledger."""
        return self._ledger

    async def _record(self, receipt: Receipt) -> Receipt:
        return await self._ledger.append(receipt)

    def register_provider(self, provider: EnvironmentProvider) -> None:
        """Register one structurally valid provider by stable name."""
        if not isinstance(provider, EnvironmentProvider):
            raise TypeError("provider does not satisfy EnvironmentProvider")
        if not _PROVIDER_NAME.fullmatch(provider.name):
            raise ValueError("provider name must match [A-Za-z0-9_.-]{1,256}")
        if not isinstance(provider.materialization_requires_authority, bool):
            raise TypeError("provider.materialization_requires_authority must be boolean")
        if provider.name in self._providers:
            raise ValueError(f"provider already registered: {provider.name}")
        self._providers[provider.name] = provider

    def discover(self) -> tuple[str, ...]:
        """Return registered provider names without materializing a world."""
        return tuple(sorted(self._providers))

    def _payload_within_limit(self, value: object) -> bool:
        return len(canonical_json_bytes(value)) <= self.limits.max_payload_bytes

    async def _authority_decision(
        self,
        *,
        required: bool,
        episode_id: str,
        subject_ref: str,
        operation: Operation,
        capability_ref: str,
        payload: JsonObject,
        authority_ref: str | None,
    ) -> AuthorityDecision:
        if not required:
            return AuthorityDecision(admitted=True, reason="AUTHORITY_NOT_REQUIRED")
        request = AuthorityRequest(
            episode_id=episode_id,
            subject_ref=subject_ref,
            operation=operation,
            capability_ref=capability_ref,
            payload=payload,
            authority_ref=authority_ref,
        )
        try:
            with anyio.fail_after(self.limits.authority_timeout_s):
                return await self._authority.authorize(request)
        except TimeoutError:
            return AuthorityDecision(
                admitted=False,
                reason="AUTHORITY_RESOLUTION_TIMEOUT",
                error_type="TimeoutError",
                error_digest=digest_text("authority-resolution-timeout"),
            )
        except Exception as exc:  # external policy decision points are fail-closed
            return AuthorityDecision(
                admitted=False,
                reason="AUTHORITY_RESOLVER_ERROR",
                error_type=type(exc).__name__,
                error_digest=digest_text(str(exc)),
            )

    async def _observe_environment(
        self, environment: Environment, episode_id: str
    ) -> Observation:
        try:
            with anyio.fail_after(self.limits.provider_timeout_s):
                value = await environment.observe()
        except TimeoutError as exc:
            raise GymActOperationError("provider observation timed out") from exc
        if not isinstance(value, dict):
            raise GymActOperationError("provider observation must be a JSON object")
        if len(canonical_json_bytes(value)) > self.limits.max_state_bytes:
            raise GymActOperationError("observed state exceeds configured size limit")
        return Observation(
            episode_id=episode_id,
            state=value,
            state_digest=digest_json(value),
        )

    async def _observe_unlocked(self, state: _EpisodeState) -> Observation:
        return await self._observe_environment(state.environment, state.episode.episode_id)

    async def _safe_post_observation(
        self, state: _EpisodeState
    ) -> tuple[Observation | None, str | None, str | None]:
        try:
            return await self._observe_unlocked(state), None, None
        except Exception as exc:
            return None, type(exc).__name__, digest_text(str(exc))

    async def materialize(self, intent: MaterializationIntent) -> MaterializationResult:
        """Materialize a bounded world with authority, replay, and write-ahead evidence."""
        intent_digest = digest_json(intent.model_dump(mode="json"))
        async with self._materialization_lock:
            cached = self._materialization_idempotency.get(intent.idempotency_key)
            if cached is not None:
                if cached.intent_digest == intent_digest:
                    return cached.result
                prior = cached.result.receipt
                receipt = await self._record(
                    Receipt(
                        episode_id=prior.episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.REFUSED,
                        subject_ref=prior.subject_ref,
                        capability_ref="urn:gymact:operation:materialize",
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        reason="IDEMPOTENCY_KEY_CONFLICT",
                    )
                )
                return MaterializationResult(
                    accepted=False, standing=Standing.REFUSED, receipt=receipt
                )

            episode_id = uuid4().hex
            subject_ref = f"urn:gymact:provider:{intent.provider}"
            capability_ref = "urn:gymact:operation:materialize"
            if not self._payload_within_limit(intent.config):
                receipt = await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.REFUSED,
                        subject_ref=subject_ref,
                        capability_ref=capability_ref,
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        reason="PAYLOAD_LIMIT_EXCEEDED",
                    )
                )
                result = MaterializationResult(
                    accepted=False, standing=Standing.REFUSED, receipt=receipt
                )
                self._materialization_idempotency[intent.idempotency_key] = (
                    _MaterializationRecord(intent_digest, result)
                )
                return result

            provider = self._providers.get(intent.provider)
            if provider is None:
                receipt = await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.UNSUPPORTED,
                        subject_ref=subject_ref,
                        capability_ref=capability_ref,
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        reason="UNKNOWN_PROVIDER",
                    )
                )
                result = MaterializationResult(
                    accepted=False, standing=Standing.UNSUPPORTED, receipt=receipt
                )
                self._materialization_idempotency[intent.idempotency_key] = (
                    _MaterializationRecord(intent_digest, result)
                )
                return result

            authority = await self._authority_decision(
                required=provider.materialization_requires_authority,
                episode_id=episode_id,
                subject_ref=subject_ref,
                operation=Operation.MATERIALIZE,
                capability_ref=capability_ref,
                payload={"scenario": intent.scenario, "config": intent.config},
                authority_ref=intent.authority_ref,
            )
            if not authority.admitted:
                receipt = await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.REFUSED,
                        subject_ref=subject_ref,
                        capability_ref=capability_ref,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        reason=authority.reason,
                        error_type=authority.error_type,
                        error_digest=authority.error_digest,
                    )
                )
                result = MaterializationResult(
                    accepted=False, standing=Standing.REFUSED, receipt=receipt
                )
                self._materialization_idempotency[intent.idempotency_key] = (
                    _MaterializationRecord(intent_digest, result)
                )
                return result

            prepared = await self._record(
                Receipt(
                    episode_id=episode_id,
                    operation=Operation.MATERIALIZE,
                    stage=ReceiptStage.PREPARED,
                    standing=Standing.PARTIAL_ALIVE,
                    subject_ref=subject_ref,
                    capability_ref=capability_ref,
                    authority_ref=intent.authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    idempotency_key=intent.idempotency_key,
                    reason="ACTUATION_PREPARED",
                )
            )
            try:
                with anyio.fail_after(self.limits.provider_timeout_s):
                    environment = await provider.materialize(
                        scenario=intent.scenario,
                        config=intent.config,
                    )
            except TimeoutError:
                receipt = await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.BLOCKED,
                        subject_ref=subject_ref,
                        capability_ref=capability_ref,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        prepared_receipt_digest=prepared.receipt_digest,
                        reason="PROVIDER_TIMEOUT",
                        error_type="TimeoutError",
                        error_digest=digest_text("materialization-timeout"),
                    )
                )
                result = MaterializationResult(
                    accepted=False, standing=Standing.BLOCKED, receipt=receipt
                )
                self._materialization_idempotency[intent.idempotency_key] = (
                    _MaterializationRecord(intent_digest, result)
                )
                return result
            except Exception as exc:
                receipt = await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.BLOCKED,
                        subject_ref=subject_ref,
                        capability_ref=capability_ref,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        prepared_receipt_digest=prepared.receipt_digest,
                        reason="PROVIDER_ERROR",
                        error_type=type(exc).__name__,
                        error_digest=digest_text(str(exc)),
                    )
                )
                result = MaterializationResult(
                    accepted=False, standing=Standing.BLOCKED, receipt=receipt
                )
                self._materialization_idempotency[intent.idempotency_key] = (
                    _MaterializationRecord(intent_digest, result)
                )
                return result

            cleanup_error: Exception | None = None
            try:
                if not isinstance(environment, Environment):
                    raise TypeError("materialized object does not satisfy Environment")
                if not isinstance(environment.requires_authority, bool):
                    raise TypeError("environment.requires_authority must be boolean")
                capabilities = tuple(environment.capabilities())
                if not all(isinstance(item, Capability) for item in capabilities):
                    raise TypeError("environment capabilities must be Capability values")
                validation = self.profile.validate_capabilities(capabilities)
                if not validation.conforms:
                    raise ValueError("provider capabilities do not conform to GymAct profile")
                episode = Episode(
                    episode_id=episode_id,
                    provider=intent.provider,
                    environment_id=environment.environment_id,
                    scenario=intent.scenario,
                )
                observation = await self._observe_environment(environment, episode_id)
            except Exception as exc:
                admission_error = exc
                try:
                    with anyio.fail_after(self.limits.provider_timeout_s):
                        await environment.teardown()
                except Exception as cleanup_exc:
                    cleanup_error = cleanup_exc
                reason = (
                    "ENVIRONMENT_ADMISSION_FAILED_CLEANUP_BLOCKED"
                    if cleanup_error is not None
                    else "ENVIRONMENT_ADMISSION_FAILED"
                )
                detail = str(admission_error)
                if cleanup_error is not None:
                    detail += f"|cleanup:{type(cleanup_error).__name__}:{cleanup_error}"
                receipt = await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.BLOCKED,
                        subject_ref=getattr(environment, "environment_id", subject_ref),
                        capability_ref=capability_ref,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        prepared_receipt_digest=prepared.receipt_digest,
                        reason=reason,
                        error_type=type(admission_error).__name__,
                        error_digest=digest_text(detail),
                    )
                )
                result = MaterializationResult(
                    accepted=False, standing=Standing.BLOCKED, receipt=receipt
                )
                self._materialization_idempotency[intent.idempotency_key] = (
                    _MaterializationRecord(intent_digest, result)
                )
                return result

            self._episodes[episode_id] = _EpisodeState(episode, environment)
            receipt = await self._record(
                Receipt(
                    episode_id=episode_id,
                    operation=Operation.MATERIALIZE,
                    standing=Standing.ALIVE,
                    subject_ref=environment.environment_id,
                    capability_ref=capability_ref,
                    authority_ref=intent.authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    idempotency_key=intent.idempotency_key,
                    post_state_digest=observation.state_digest,
                    prepared_receipt_digest=prepared.receipt_digest,
                    reason="MATERIALIZATION_OBSERVED",
                )
            )
            result = MaterializationResult(
                accepted=True,
                standing=Standing.ALIVE,
                episode=episode,
                observation=observation,
                receipt=receipt,
            )
            self._materialization_idempotency[intent.idempotency_key] = (
                _MaterializationRecord(intent_digest, result)
            )
            return result

    async def create_episode(
        self,
        provider: str,
        *,
        scenario: str | None = None,
        config: JsonObject | None = None,
        authority_ref: str | None = None,
        idempotency_key: str | None = None,
    ) -> MaterializationResult:
        """Convenience wrapper around fully receipted materialization."""
        values: dict[str, Any] = {
            "provider": provider,
            "scenario": scenario,
            "config": config or {},
            "authority_ref": authority_ref,
        }
        if idempotency_key is not None:
            values["idempotency_key"] = idempotency_key
        return await self.materialize(MaterializationIntent.model_validate(values))

    def _state(self, episode_id: str) -> _EpisodeState:
        try:
            return self._episodes[episode_id]
        except KeyError as exc:
            raise KeyError(f"unknown episode: {episode_id}") from exc

    def capabilities(self, episode_id: str) -> tuple[Capability, ...]:
        """Return admitted semantic capabilities exposed by one environment."""
        return tuple(self._state(episode_id).environment.capabilities())

    async def observe(self, episode_id: str) -> Observation:
        """Observe current state without promoting it to verification."""
        state = self._state(episode_id)
        async with state.lock:
            return await self._observe_unlocked(state)

    async def act(self, intent: ActuationIntent) -> ActuationResult:
        """Attempt one semantic capability actuation with authority and replay gates."""
        state = self._state(intent.episode_id)
        key = (intent.episode_id, intent.idempotency_key)
        intent_digest = digest_json(intent.model_dump(mode="json"))

        async with state.lock:
            cached = self._actuation_idempotency.get(key)
            if cached is not None:
                if cached.intent_digest == intent_digest:
                    return cached.result
                before = await self._observe_unlocked(state)
                receipt = await self._record(
                    Receipt(
                        episode_id=intent.episode_id,
                        operation=Operation.ACT,
                        standing=Standing.REFUSED,
                        subject_ref=state.environment.environment_id,
                        capability_ref=intent.capability,
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason="IDEMPOTENCY_KEY_CONFLICT",
                    )
                )
                return ActuationResult(
                    accepted=False,
                    standing=Standing.REFUSED,
                    observation=before,
                    receipt=receipt,
                )

            if not self._payload_within_limit(intent.payload):
                before = await self._observe_unlocked(state)
                receipt = await self._record(
                    Receipt(
                        episode_id=intent.episode_id,
                        operation=Operation.ACT,
                        standing=Standing.REFUSED,
                        subject_ref=state.environment.environment_id,
                        capability_ref=intent.capability,
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason="PAYLOAD_LIMIT_EXCEEDED",
                    )
                )
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.REFUSED,
                    observation=before,
                    receipt=receipt,
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result

            before = await self._observe_unlocked(state)
            capability = {item.iri: item for item in state.environment.capabilities()}.get(
                intent.capability
            )
            if capability is None:
                receipt = await self._record(
                    Receipt(
                        episode_id=intent.episode_id,
                        operation=Operation.ACT,
                        standing=Standing.UNSUPPORTED,
                        subject_ref=state.environment.environment_id,
                        capability_ref=intent.capability,
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason="UNKNOWN_CAPABILITY",
                    )
                )
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.UNSUPPORTED,
                    observation=before,
                    receipt=receipt,
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result
            if capability.consequence is not Consequence.DO:
                receipt = await self._record(
                    Receipt(
                        episode_id=intent.episode_id,
                        operation=Operation.ACT,
                        standing=Standing.REFUSED,
                        subject_ref=state.environment.environment_id,
                        capability_ref=capability.iri,
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason="READ_CAPABILITY_IS_NOT_ACTUATION",
                    )
                )
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.REFUSED,
                    observation=before,
                    receipt=receipt,
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result

            authority = await self._authority_decision(
                required=state.environment.requires_authority,
                episode_id=intent.episode_id,
                subject_ref=state.environment.environment_id,
                operation=Operation.ACT,
                capability_ref=capability.iri,
                payload=intent.payload,
                authority_ref=intent.authority_ref,
            )
            if not authority.admitted:
                receipt = await self._record(
                    Receipt(
                        episode_id=intent.episode_id,
                        operation=Operation.ACT,
                        standing=Standing.REFUSED,
                        subject_ref=state.environment.environment_id,
                        capability_ref=capability.iri,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason=authority.reason,
                        error_type=authority.error_type,
                        error_digest=authority.error_digest,
                    )
                )
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.REFUSED,
                    observation=before,
                    receipt=receipt,
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result

            prepared = await self._record(
                Receipt(
                    episode_id=intent.episode_id,
                    operation=Operation.ACT,
                    stage=ReceiptStage.PREPARED,
                    standing=Standing.PARTIAL_ALIVE,
                    subject_ref=state.environment.environment_id,
                    capability_ref=capability.iri,
                    authority_ref=intent.authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    idempotency_key=intent.idempotency_key,
                    pre_state_digest=before.state_digest,
                    reason="ACTUATION_PREPARED",
                )
            )
            try:
                with anyio.fail_after(self.limits.provider_timeout_s):
                    effect = await state.environment.actuate(capability, intent.payload)
                if not isinstance(effect, dict):
                    raise TypeError("provider effect must be a JSON object")
                if len(canonical_json_bytes(effect)) > self.limits.max_state_bytes:
                    raise ValueError("provider effect exceeds configured size limit")
            except TimeoutError:
                after, post_error_type, post_error_digest = await self._safe_post_observation(state)
                receipt = await self._record(
                    Receipt(
                        episode_id=intent.episode_id,
                        operation=Operation.ACT,
                        standing=Standing.BLOCKED,
                        subject_ref=state.environment.environment_id,
                        capability_ref=capability.iri,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=after.state_digest if after else None,
                        prepared_receipt_digest=prepared.receipt_digest,
                        reason="PROVIDER_TIMEOUT",
                        error_type=post_error_type or "TimeoutError",
                        error_digest=post_error_digest or digest_text("actuation-timeout"),
                    )
                )
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.BLOCKED,
                    observation=after,
                    receipt=receipt,
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result
            except Exception as exc:
                after, _, _ = await self._safe_post_observation(state)
                receipt = await self._record(
                    Receipt(
                        episode_id=intent.episode_id,
                        operation=Operation.ACT,
                        standing=Standing.BLOCKED,
                        subject_ref=state.environment.environment_id,
                        capability_ref=capability.iri,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=after.state_digest if after else None,
                        prepared_receipt_digest=prepared.receipt_digest,
                        reason="PROVIDER_ERROR",
                        error_type=type(exc).__name__,
                        error_digest=digest_text(str(exc)),
                    )
                )
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.BLOCKED,
                    observation=after,
                    receipt=receipt,
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result

            after, post_error_type, post_error_digest = await self._safe_post_observation(state)
            if after is None:
                receipt = await self._record(
                    Receipt(
                        episode_id=intent.episode_id,
                        operation=Operation.ACT,
                        standing=Standing.BLOCKED,
                        subject_ref=state.environment.environment_id,
                        capability_ref=capability.iri,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        prepared_receipt_digest=prepared.receipt_digest,
                        reason="POST_ACTUATION_OBSERVATION_FAILED",
                        error_type=post_error_type,
                        error_digest=post_error_digest,
                    )
                )
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.BLOCKED,
                    effect=effect,
                    receipt=receipt,
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result

            receipt = await self._record(
                Receipt(
                    episode_id=intent.episode_id,
                    operation=Operation.ACT,
                    standing=Standing.ALIVE,
                    subject_ref=state.environment.environment_id,
                    capability_ref=capability.iri,
                    authority_ref=intent.authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    idempotency_key=intent.idempotency_key,
                    pre_state_digest=before.state_digest,
                    post_state_digest=after.state_digest,
                    prepared_receipt_digest=prepared.receipt_digest,
                    reason="CONSEQUENCE_OBSERVED",
                )
            )
            result = ActuationResult(
                accepted=True,
                standing=Standing.ALIVE,
                effect=effect,
                observation=after,
                receipt=receipt,
            )
            self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
            return result

    async def verify(self, episode_id: str, expected: JsonObject) -> VerificationResult:
        """Run provider verification and record the independent verdict as evidence."""
        state = self._state(episode_id)
        async with state.lock:
            try:
                with anyio.fail_after(self.limits.provider_timeout_s):
                    passed, observed = await state.environment.verify(expected)
                if not isinstance(observed, dict):
                    raise TypeError("verification observation must be a JSON object")
                if len(canonical_json_bytes(observed)) > self.limits.max_state_bytes:
                    raise GymActOperationError("verification state exceeds configured size limit")
            except Exception as exc:
                receipt = await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.VERIFY,
                        standing=Standing.BLOCKED,
                        subject_ref=state.environment.environment_id,
                        capability_ref="urn:gymact:operation:verify",
                        reason="VERIFICATION_EXECUTION_FAILED",
                        error_type=type(exc).__name__,
                        error_digest=digest_text(str(exc)),
                    )
                )
                raise GymActOperationError("verification execution failed", receipt=receipt) from exc

            result = VerificationResult(
                episode_id=episode_id,
                passed=passed,
                expected=expected,
                observed=observed,
                state_digest=digest_json(observed),
            )
            receipt = await self._record(
                Receipt(
                    episode_id=episode_id,
                    operation=Operation.VERIFY,
                    standing=Standing.ALIVE,
                    subject_ref=state.environment.environment_id,
                    capability_ref="urn:gymact:operation:verify",
                    post_state_digest=result.state_digest,
                    verification_id=result.verification_id,
                    reason="VERIFICATION_PASSED" if passed else "VERIFICATION_FAILED",
                )
            )
            return result.model_copy(update={"receipt_id": receipt.receipt_id})

    async def checkpoint(self, episode_id: str) -> JsonObject:
        """Return bounded provider-defined recovery state."""
        state = self._state(episode_id)
        async with state.lock:
            try:
                with anyio.fail_after(self.limits.provider_timeout_s):
                    checkpoint = await state.environment.checkpoint()
            except TimeoutError as exc:
                raise GymActOperationError("checkpoint timed out") from exc
            if not isinstance(checkpoint, dict):
                raise GymActOperationError("checkpoint must be a JSON object")
            if len(canonical_json_bytes(checkpoint)) > self.limits.max_state_bytes:
                raise GymActOperationError("checkpoint exceeds configured size limit")
            return checkpoint

    async def restore(
        self, episode_id: str, checkpoint: JsonObject, *, authority_ref: str | None = None
    ) -> Receipt:
        """Restore a checkpoint with the same write-ahead authority/evidence law."""
        state = self._state(episode_id)
        async with state.lock:
            before = await self._observe_unlocked(state)
            if not self._payload_within_limit(checkpoint):
                return await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.RESTORE,
                        standing=Standing.REFUSED,
                        subject_ref=state.environment.environment_id,
                        capability_ref="urn:gymact:operation:restore",
                        authority_ref=authority_ref,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason="PAYLOAD_LIMIT_EXCEEDED",
                    )
                )
            authority = await self._authority_decision(
                required=state.environment.requires_authority,
                episode_id=episode_id,
                subject_ref=state.environment.environment_id,
                operation=Operation.RESTORE,
                capability_ref="urn:gymact:operation:restore",
                payload={"checkpoint_digest": digest_json(checkpoint)},
                authority_ref=authority_ref,
            )
            if not authority.admitted:
                return await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.RESTORE,
                        standing=Standing.REFUSED,
                        subject_ref=state.environment.environment_id,
                        capability_ref="urn:gymact:operation:restore",
                        authority_ref=authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason=authority.reason,
                        error_type=authority.error_type,
                        error_digest=authority.error_digest,
                    )
                )
            prepared = await self._record(
                Receipt(
                    episode_id=episode_id,
                    operation=Operation.RESTORE,
                    stage=ReceiptStage.PREPARED,
                    standing=Standing.PARTIAL_ALIVE,
                    subject_ref=state.environment.environment_id,
                    capability_ref="urn:gymact:operation:restore",
                    authority_ref=authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    pre_state_digest=before.state_digest,
                    reason="ACTUATION_PREPARED",
                )
            )
            try:
                with anyio.fail_after(self.limits.provider_timeout_s):
                    await state.environment.restore(checkpoint)
            except Exception as exc:
                after, _, _ = await self._safe_post_observation(state)
                return await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.RESTORE,
                        standing=Standing.BLOCKED,
                        subject_ref=state.environment.environment_id,
                        capability_ref="urn:gymact:operation:restore",
                        authority_ref=authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        pre_state_digest=before.state_digest,
                        post_state_digest=after.state_digest if after else None,
                        prepared_receipt_digest=prepared.receipt_digest,
                        reason="PROVIDER_TIMEOUT" if isinstance(exc, TimeoutError) else "PROVIDER_ERROR",
                        error_type=type(exc).__name__,
                        error_digest=digest_text(str(exc)),
                    )
                )
            after, error_type, error_digest = await self._safe_post_observation(state)
            if after is None:
                return await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.RESTORE,
                        standing=Standing.BLOCKED,
                        subject_ref=state.environment.environment_id,
                        capability_ref="urn:gymact:operation:restore",
                        authority_ref=authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        pre_state_digest=before.state_digest,
                        prepared_receipt_digest=prepared.receipt_digest,
                        reason="POST_ACTUATION_OBSERVATION_FAILED",
                        error_type=error_type,
                        error_digest=error_digest,
                    )
                )
            return await self._record(
                Receipt(
                    episode_id=episode_id,
                    operation=Operation.RESTORE,
                    standing=Standing.ALIVE,
                    subject_ref=state.environment.environment_id,
                    capability_ref="urn:gymact:operation:restore",
                    authority_ref=authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    pre_state_digest=before.state_digest,
                    post_state_digest=after.state_digest,
                    prepared_receipt_digest=prepared.receipt_digest,
                    reason="CONSEQUENCE_OBSERVED",
                )
            )

    async def teardown(self, episode_id: str, *, authority_ref: str | None = None) -> Receipt:
        """Idempotently tear down a world after authority and a write-ahead receipt."""
        prior = self._teardown_receipts.get(episode_id)
        if prior is not None:
            return prior
        state = self._state(episode_id)
        async with state.lock:
            before = await self._observe_unlocked(state)
            authority = await self._authority_decision(
                required=state.environment.requires_authority,
                episode_id=episode_id,
                subject_ref=state.environment.environment_id,
                operation=Operation.TEARDOWN,
                capability_ref="urn:gymact:operation:teardown",
                payload={},
                authority_ref=authority_ref,
            )
            if not authority.admitted:
                return await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.TEARDOWN,
                        standing=Standing.REFUSED,
                        subject_ref=state.environment.environment_id,
                        capability_ref="urn:gymact:operation:teardown",
                        authority_ref=authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason=authority.reason,
                        error_type=authority.error_type,
                        error_digest=authority.error_digest,
                    )
                )
            prepared = await self._record(
                Receipt(
                    episode_id=episode_id,
                    operation=Operation.TEARDOWN,
                    stage=ReceiptStage.PREPARED,
                    standing=Standing.PARTIAL_ALIVE,
                    subject_ref=state.environment.environment_id,
                    capability_ref="urn:gymact:operation:teardown",
                    authority_ref=authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    pre_state_digest=before.state_digest,
                    reason="ACTUATION_PREPARED",
                )
            )
            try:
                with anyio.fail_after(self.limits.provider_timeout_s):
                    await state.environment.teardown()
            except Exception as exc:
                return await self._record(
                    Receipt(
                        episode_id=episode_id,
                        operation=Operation.TEARDOWN,
                        standing=Standing.BLOCKED,
                        subject_ref=state.environment.environment_id,
                        capability_ref="urn:gymact:operation:teardown",
                        authority_ref=authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        pre_state_digest=before.state_digest,
                        prepared_receipt_digest=prepared.receipt_digest,
                        reason="PROVIDER_TIMEOUT" if isinstance(exc, TimeoutError) else "PROVIDER_ERROR",
                        error_type=type(exc).__name__,
                        error_digest=digest_text(str(exc)),
                    )
                )
            receipt = await self._record(
                Receipt(
                    episode_id=episode_id,
                    operation=Operation.TEARDOWN,
                    standing=Standing.ALIVE,
                    subject_ref=state.environment.environment_id,
                    capability_ref="urn:gymact:operation:teardown",
                    authority_ref=authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    pre_state_digest=before.state_digest,
                    prepared_receipt_digest=prepared.receipt_digest,
                    reason="TEARDOWN_COMPLETED",
                )
            )
            self._teardown_receipts[episode_id] = receipt
            del self._episodes[episode_id]
            return receipt

    async def receipts(self, episode_id: str | None = None) -> tuple[Receipt, ...]:
        """Read the append-only receipt ledger."""
        return await self._ledger.receipts(episode_id)

    async def verify_evidence_chain(self) -> bool:
        """Verify the complete configured BLAKE3 receipt chain."""
        return await self._ledger.verify_chain()

    async def provenance(self):
        """Return a public PROV-O/SOSA graph over the current receipt ledger."""
        return receipts_to_prov(await self._ledger.receipts())
