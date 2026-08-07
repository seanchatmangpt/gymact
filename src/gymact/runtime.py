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
    Episode,
    Observation,
    Operation,
    Receipt,
    Standing,
    VerificationResult,
)
from gymact.providers import Environment, EnvironmentProvider
from gymact.semantic import ProfileAuthority


def _digest(value: dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass
class _EpisodeState:
    episode: Episode
    environment: Environment
    lock: anyio.Lock = field(default_factory=anyio.Lock)


@dataclass(frozen=True)
class _IdempotencyRecord:
    intent_digest: str
    result: ActuationResult


class GymAct:
    """Reference orchestrator that keeps transport and benchmark semantics separate."""

    def __init__(
        self,
        *,
        validate_profile: bool = True,
        authority_resolver: AuthorityResolver | None = None,
    ) -> None:
        self._providers: dict[str, EnvironmentProvider] = {}
        self._episodes: dict[str, _EpisodeState] = {}
        self._idempotency: dict[tuple[str, str], _IdempotencyRecord] = {}
        self._authority = authority_resolver or DenyAuthorityResolver()
        self.profile = ProfileAuthority()
        if validate_profile:
            result = self.profile.validate()
            if not result.conforms:
                raise RuntimeError(f"GymAct semantic profile invalid: {result.report_text}")

    def register_provider(self, provider: EnvironmentProvider) -> None:
        """Register one provider by stable name; duplicate names are refused."""
        if provider.name in self._providers:
            raise ValueError(f"provider already registered: {provider.name}")
        self._providers[provider.name] = provider

    def discover(self) -> tuple[str, ...]:
        """Return registered provider names without materializing a world."""
        return tuple(sorted(self._providers))

    async def create_episode(
        self, provider: str, *, scenario: str | None = None, config: dict[str, Any] | None = None
    ) -> Episode:
        """Materialize a provider environment and bind one bounded episode to it."""
        try:
            factory = self._providers[provider]
        except KeyError as exc:
            raise KeyError(f"unknown provider: {provider}") from exc
        environment = await factory.materialize(scenario=scenario, config=config or {})
        episode = Episode(
            episode_id=uuid4().hex,
            provider=provider,
            environment_id=environment.environment_id,
            scenario=scenario,
        )
        self._episodes[episode.episode_id] = _EpisodeState(episode, environment)
        return episode

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

    async def _authorize(
        self,
        state: _EpisodeState,
        *,
        operation: Operation,
        affordance: str,
        payload: dict[str, Any],
        authority_ref: str | None,
    ) -> AuthorityDecision:
        if not state.environment.requires_authority:
            return AuthorityDecision(admitted=True, reason="AUTHORITY_NOT_REQUIRED")
        return await self._authority.authorize(
            AuthorityRequest(
                episode_id=state.episode.episode_id,
                environment_id=state.environment.environment_id,
                operation=operation,
                affordance=affordance,
                payload=payload,
                authority_ref=authority_ref,
            )
        )

    async def observe(self, episode_id: str) -> Observation:
        """Observe current state without promoting it to verification."""
        state = self._state(episode_id)
        async with state.lock:
            return await self._observe_unlocked(state)

    async def act(self, intent: ActuationIntent) -> ActuationResult:
        """Attempt one actuation with authority, concurrency and idempotency gates."""
        state = self._state(intent.episode_id)
        key = (intent.episode_id, intent.idempotency_key)
        intent_digest = _digest(intent.model_dump(mode="json"))

        async with state.lock:
            cached = self._idempotency.get(key)
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
                        operation=intent.operation,
                        standing=Standing.REFUSED,
                        affordance=intent.affordance,
                        authority_ref=intent.authority_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason="IDEMPOTENCY_KEY_CONFLICT",
                    ),
                )

            before = await self._observe_unlocked(state)
            authority = await self._authorize(
                state,
                operation=intent.operation,
                affordance=intent.affordance,
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
                        operation=intent.operation,
                        standing=Standing.REFUSED,
                        affordance=intent.affordance,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=before.state_digest,
                        reason=authority.reason,
                    ),
                )
                self._idempotency[key] = _IdempotencyRecord(intent_digest, result)
                return result

            try:
                effect = await state.environment.actuate(intent.affordance, intent.payload)
            except Exception as exc:  # provider/tool failures become evidence, not disappearance
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
                        operation=intent.operation,
                        standing=Standing.BLOCKED,
                        affordance=intent.affordance,
                        authority_ref=intent.authority_ref,
                        authority_evidence_ref=authority.evidence_ref,
                        idempotency_key=intent.idempotency_key,
                        pre_state_digest=before.state_digest,
                        post_state_digest=after.state_digest,
                        reason=f"PROVIDER_ERROR:{type(exc).__name__}:{exc}",
                    ),
                )
                self._idempotency[key] = _IdempotencyRecord(intent_digest, result)
                return result

            after = await self._observe_unlocked(state)
            result = ActuationResult(
                accepted=True,
                standing=Standing.ALIVE,
                effect=effect,
                observation=after,
                receipt=Receipt(
                    episode_id=intent.episode_id,
                    operation=intent.operation,
                    standing=Standing.ALIVE,
                    affordance=intent.affordance,
                    authority_ref=intent.authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    idempotency_key=intent.idempotency_key,
                    pre_state_digest=before.state_digest,
                    post_state_digest=after.state_digest,
                ),
            )
            self._idempotency[key] = _IdempotencyRecord(intent_digest, result)
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
            authority = await self._authorize(
                state,
                operation=Operation.RESTORE,
                affordance="restore",
                payload={"checkpoint_digest": _digest(checkpoint)},
                authority_ref=authority_ref,
            )
            if not authority.admitted:
                return Receipt(
                    episode_id=episode_id,
                    operation=Operation.RESTORE,
                    standing=Standing.REFUSED,
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
                    authority_ref=authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    pre_state_digest=before.state_digest,
                    post_state_digest=after.state_digest,
                    reason=f"PROVIDER_ERROR:{type(exc).__name__}:{exc}",
                )
            return Receipt(
                episode_id=episode_id,
                operation=Operation.RESTORE,
                standing=Standing.ALIVE,
                authority_ref=authority_ref,
                authority_evidence_ref=authority.evidence_ref,
                pre_state_digest=before.state_digest,
                post_state_digest=after.state_digest,
            )

    async def teardown(self, episode_id: str, *, authority_ref: str | None = None) -> Receipt:
        """Tear down an environment only after an explicit authority decision when required."""
        state = self._state(episode_id)
        async with state.lock:
            before = await self._observe_unlocked(state)
            authority = await self._authorize(
                state,
                operation=Operation.TEARDOWN,
                affordance="teardown",
                payload={},
                authority_ref=authority_ref,
            )
            if not authority.admitted:
                return Receipt(
                    episode_id=episode_id,
                    operation=Operation.TEARDOWN,
                    standing=Standing.REFUSED,
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
                    authority_ref=authority_ref,
                    authority_evidence_ref=authority.evidence_ref,
                    pre_state_digest=before.state_digest,
                    reason=f"PROVIDER_ERROR:{type(exc).__name__}:{exc}",
                )
            del self._episodes[episode_id]
            return Receipt(
                episode_id=episode_id,
                operation=Operation.TEARDOWN,
                standing=Standing.ALIVE,
                authority_ref=authority_ref,
                authority_evidence_ref=authority.evidence_ref,
                pre_state_digest=before.state_digest,
            )
