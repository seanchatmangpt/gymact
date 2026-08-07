"""Small semantic runtime for bounded executable worlds."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import anyio

from gymact.authority import AuthorityResolver, DenyAuthorityResolver
from gymact.models import (
    ActuationIntent,
    ActuationResult,
    AuthorityDecision,
    AuthorityRequest,
    Capability,
    Consequence,
    Episode,
    MaterializationIntent,
    MaterializationResult,
    Observation,
    Operation,
    Receipt,
    Standing,
    VerificationResult,
)
from gymact.providers import Environment, EnvironmentProvider
from gymact.semantic import ProfileAuthority


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _error_digest(exc: Exception) -> str:
    return _digest({"type": type(exc).__name__, "message": str(exc)})


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
    """Reference orchestrator that keeps semantic identity above provider bindings."""

    def __init__(
        self,
        *,
        validate_profile: bool = True,
        authority_resolver: AuthorityResolver | None = None,
    ) -> None:
        self._providers: dict[str, EnvironmentProvider] = {}
        self._episodes: dict[str, _EpisodeState] = {}
        self._actuation_idempotency: dict[tuple[str, str], _ActuationRecord] = {}
        self._materialization_idempotency: dict[str, _MaterializationRecord] = {}
        self._materialization_lock = anyio.Lock()
        self._teardown_receipts: dict[str, Receipt] = {}
        self._authority = authority_resolver or DenyAuthorityResolver()
        self.profile = ProfileAuthority()
        if validate_profile:
            result = self.profile.validate()
            if not result.conforms:
                raise RuntimeError(f"GymAct semantic profile invalid: {result.report_text}")

    def register_provider(self, provider: EnvironmentProvider) -> None:
        """Register one provider by stable name; duplicate names are refused."""
        if not isinstance(provider, EnvironmentProvider):
            raise TypeError("provider does not satisfy EnvironmentProvider")
        if provider.name in self._providers:
            raise ValueError(f"provider already registered: {provider.name}")
        self._providers[provider.name] = provider

    def discover(self) -> tuple[str, ...]:
        """Return registered provider names without materializing a world."""
        return tuple(sorted(self._providers))

    async def _authority_decision(
        self,
        *,
        required: bool,
        episode_id: str,
        subject_ref: str,
        operation: Operation,
        capability_ref: str,
        payload: dict[str, Any],
        authority_ref: str | None,
    ) -> AuthorityDecision:
        if not required:
            return AuthorityDecision(admitted=True, reason="AUTHORITY_NOT_REQUIRED")
        return await self._authority.authorize(
            AuthorityRequest(
                episode_id=episode_id,
                subject_ref=subject_ref,
                operation=operation,
                capability_ref=capability_ref,
                payload=payload,
                authority_ref=authority_ref,
            )
        )

    async def materialize(self, intent: MaterializationIntent) -> MaterializationResult:
        """Materialize one bounded world with authority, idempotency, and semantic gates."""
        intent_digest = _digest(intent.model_dump(mode="json"))
        async with self._materialization_lock:
            cached = self._materialization_idempotency.get(intent.idempotency_key)
            if cached is not None:
                if cached.intent_digest == intent_digest:
                    return cached.result
                prior_receipt = cached.result.receipt
                return MaterializationResult(
                    accepted=False,
                    standing=Standing.REFUSED,
                    receipt=Receipt(
                        episode_id=prior_receipt.episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.REFUSED,
                        subject_ref=prior_receipt.subject_ref,
                        capability_ref="urn:gymact:operation:materialize",
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        reason="IDEMPOTENCY_KEY_CONFLICT",
                    ),
                )

            episode_id = uuid4().hex
            subject_ref = f"urn:gymact:provider:{intent.provider}"
            provider = self._providers.get(intent.provider)
            if provider is None:
                result = MaterializationResult(
                    accepted=False,
                    standing=Standing.UNSUPPORTED,
                    receipt=Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.UNSUPPORTED,
                        subject_ref=subject_ref,
                        capability_ref="urn:gymact:operation:materialize",
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        reason="UNKNOWN_PROVIDER",
                    ),
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
                capability_ref="urn:gymact:operation:materialize",
                payload={"scenario": intent.scenario, "config": intent.config},
                authority_ref=intent.authority_ref,
            )
            if not authority.admitted:
                result = MaterializationResult(
                    accepted=False,
                    standing=Standing.REFUSED,
                    receipt=Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.REFUSED,
                        subject_ref=subject_ref,
                        capability_ref="urn:gymact:operation:materialize",
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        reason=authority.reason,
                    ),
                )
                self._materialization_idempotency[intent.idempotency_key] = (
                    _MaterializationRecord(intent_digest, result)
                )
                return result

            try:
                environment = await provider.materialize(
                    scenario=intent.scenario,
                    config=intent.config,
                )
            except Exception as exc:
                result = MaterializationResult(
                    accepted=False,
                    standing=Standing.BLOCKED,
                    receipt=Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.BLOCKED,
                        subject_ref=subject_ref,
                        capability_ref="urn:gymact:operation:materialize",
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        error_digest=_error_digest(exc),
                        reason=f"PROVIDER_ERROR:{type(exc).__name__}",
                    ),
                )
                self._materialization_idempotency[intent.idempotency_key] = (
                    _MaterializationRecord(intent_digest, result)
                )
                return result

            try:
                capabilities = environment.capabilities()
                validation = self.profile.validate_capabilities(capabilities)
                if not validation.conforms:
                    raise ValueError("provider capabilities do not conform to GymAct profile")
                initial_state = await environment.observe()
            except Exception as exc:
                try:
                    await environment.teardown()
                except Exception:
                    pass
                result = MaterializationResult(
                    accepted=False,
                    standing=Standing.BLOCKED,
                    receipt=Receipt(
                        episode_id=episode_id,
                        operation=Operation.MATERIALIZE,
                        standing=Standing.BLOCKED,
                        subject_ref=getattr(environment, "environment_id", subject_ref),
                        capability_ref="urn:gymact:operation:materialize",
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        error_digest=_error_digest(exc),
                        reason="ENVIRONMENT_ADMISSION_FAILED",
                    ),
                )
                self._materialization_idempotency[intent.idempotency_key] = (
                    _MaterializationRecord(intent_digest, result)
                )
                return result

            episode = Episode(
                episode_id=episode_id,
                provider=intent.provider,
                environment_id=environment.environment_id,
                scenario=intent.scenario,
            )
            state = _EpisodeState(episode, environment)
            self._episodes[episode_id] = state
            observation = Observation(
                episode_id=episode_id,
                state=initial_state,
                state_digest=_digest(initial_state),
            )
            result = MaterializationResult(
                accepted=True,
                standing=Standing.ALIVE,
                episode=episode,
                observation=observation,
                receipt=Receipt(
                    episode_id=episode_id,
                    operation=Operation.MATERIALIZE,
                    standing=Standing.ALIVE,
                    subject_ref=environment.environment_id,
                    capability_ref="urn:gymact:operation:materialize",
                    authority_ref=intent.authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    idempotency_key=intent.idempotency_key,
                    post_state_digest=observation.state_digest,
                ),
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
        config: dict[str, Any] | None = None,
        authority_ref: str | None = None,
        idempotency_key: str | None = None,
    ) -> MaterializationResult:
        """Convenience wrapper around the fully receipted materialization operation."""
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

    async def _observe_unlocked(self, state: _EpisodeState) -> Observation:
        value = await state.environment.observe()
        return Observation(
            episode_id=state.episode.episode_id,
            state=value,
            state_digest=_digest(value),
        )

    def capabilities(self, episode_id: str) -> tuple[Capability, ...]:
        """Return the admitted semantic capabilities exposed by one environment."""
        return self._state(episode_id).environment.capabilities()

    async def observe(self, episode_id: str) -> Observation:
        """Observe current state without promoting it to verification."""
        state = self._state(episode_id)
        async with state.lock:
            return await self._observe_unlocked(state)

    async def act(self, intent: ActuationIntent) -> ActuationResult:
        """Attempt one semantic capability actuation with authority and replay gates."""
        state = self._state(intent.episode_id)
        key = (intent.episode_id, intent.idempotency_key)
        intent_digest = _digest(intent.model_dump(mode="json"))

        async with state.lock:
            cached = self._actuation_idempotency.get(key)
            if cached is not None:
                if cached.intent_digest == intent_digest:
                    return cached.result
                before = await self._observe_unlocked(state)
                return ActuationResult(
                    accepted=False,
                    standing=Standing.REFUSED,
                    observation=before,
                    receipt=Receipt(
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
                    ),
                )

            before = await self._observe_unlocked(state)
            capabilities = {item.iri: item for item in state.environment.capabilities()}
            capability = capabilities.get(intent.capability)
            if capability is None:
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.UNSUPPORTED,
                    observation=before,
                    receipt=Receipt(
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
                    ),
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result
            if capability.consequence is not Consequence.DO:
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.REFUSED,
                    observation=before,
                    receipt=Receipt(
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
                    ),
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
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.REFUSED,
                    observation=before,
                    receipt=Receipt(
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
                    ),
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result

            try:
                effect = await state.environment.actuate(capability, intent.payload)
            except Exception as exc:
                try:
                    after = await self._observe_unlocked(state)
                except Exception:
                    after = before
                result = ActuationResult(
                    accepted=False,
                    standing=Standing.BLOCKED,
                    observation=after,
                    receipt=Receipt(
                        episode_id=intent.episode_id,
                        operation=Operation.ACT,
                        standing=Standing.BLOCKED,
                        subject_ref=state.environment.environment_id,
                        capability_ref=capability.iri,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=after.state_digest,
                        error_digest=_error_digest(exc),
                        reason=f"PROVIDER_ERROR:{type(exc).__name__}",
                    ),
                )
                self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
                return result

            after = await self._observe_unlocked(state)
            result = ActuationResult(
                accepted=True,
                standing=Standing.ALIVE,
                effect=effect,
                observation=after,
                receipt=Receipt(
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
                ),
            )
            self._actuation_idempotency[key] = _ActuationRecord(intent_digest, result)
            return result

    async def verify(self, episode_id: str, expected: dict[str, Any]) -> VerificationResult:
        """Independently evaluate expected partial state against the environment."""
        state = self._state(episode_id)
        async with state.lock:
            passed, observed = await state.environment.verify(expected)
            return VerificationResult(
                episode_id=episode_id,
                passed=passed,
                expected=expected,
                observed=observed,
                state_digest=_digest(observed),
            )

    async def checkpoint(self, episode_id: str) -> dict[str, Any]:
        """Return provider-defined recovery state."""
        state = self._state(episode_id)
        async with state.lock:
            return await state.environment.checkpoint()

    async def restore(
        self, episode_id: str, checkpoint: dict[str, Any], *, authority_ref: str | None = None
    ) -> Receipt:
        """Restore a checkpoint only after an explicit authority decision when required."""
        state = self._state(episode_id)
        async with state.lock:
            before = await self._observe_unlocked(state)
            authority = await self._authority_decision(
                required=state.environment.requires_authority,
                episode_id=episode_id,
                subject_ref=state.environment.environment_id,
                operation=Operation.RESTORE,
                capability_ref="urn:gymact:operation:restore",
                payload={"checkpoint_digest": _digest(checkpoint)},
                authority_ref=authority_ref,
            )
            if not authority.admitted:
                return Receipt(
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
                )
            try:
                await state.environment.restore(checkpoint)
                after = await self._observe_unlocked(state)
            except Exception as exc:
                try:
                    after = await self._observe_unlocked(state)
                except Exception:
                    after = before
                return Receipt(
                    episode_id=episode_id,
                    operation=Operation.RESTORE,
                    standing=Standing.BLOCKED,
                    subject_ref=state.environment.environment_id,
                    capability_ref="urn:gymact:operation:restore",
                    authority_ref=authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    pre_state_digest=before.state_digest,
                    post_state_digest=after.state_digest,
                    error_digest=_error_digest(exc),
                    reason=f"PROVIDER_ERROR:{type(exc).__name__}",
                )
            return Receipt(
                episode_id=episode_id,
                operation=Operation.RESTORE,
                standing=Standing.ALIVE,
                subject_ref=state.environment.environment_id,
                capability_ref="urn:gymact:operation:restore",
                authority_ref=authority_ref,
                authority_evidence_ref=authority.evidence_ref,
                pre_state_digest=before.state_digest,
                post_state_digest=after.state_digest,
            )

    async def teardown(self, episode_id: str, *, authority_ref: str | None = None) -> Receipt:
        """Idempotently tear down an environment after authority admission when required."""
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
                return Receipt(
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
                )
            try:
                await state.environment.teardown()
            except Exception as exc:
                return Receipt(
                    episode_id=episode_id,
                    operation=Operation.TEARDOWN,
                    standing=Standing.BLOCKED,
                    subject_ref=state.environment.environment_id,
                    capability_ref="urn:gymact:operation:teardown",
                    authority_ref=authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    pre_state_digest=before.state_digest,
                    error_digest=_error_digest(exc),
                    reason=f"PROVIDER_ERROR:{type(exc).__name__}",
                )
            receipt = Receipt(
                episode_id=episode_id,
                operation=Operation.TEARDOWN,
                standing=Standing.ALIVE,
                subject_ref=state.environment.environment_id,
                capability_ref="urn:gymact:operation:teardown",
                authority_ref=authority_ref,
                authority_evidence_ref=authority.evidence_ref,
                pre_state_digest=before.state_digest,
            )
            self._teardown_receipts[episode_id] = receipt
            del self._episodes[episode_id]
            return receipt
