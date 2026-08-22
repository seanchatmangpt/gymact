"""EnvHarness Stage/Contract/Chain composition above GymAct's BRCE boundary.

Implements Huang et al., arXiv:2608.19880 while preserving GymAct law: Stage
mutations use ``GymAct.act``; Contract emits declarative intent transforms only;
Chain verifies every serial leg through the original ``GymAct.verify`` path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from gymact.evidence import digest
from gymact.kernel import GymAct
from gymact.models import (
    ActuationIntent,
    ActuationResult,
    Capability,
    Consequence,
    MaterializationIntent,
    MaterializationResult,
    Observation,
    Receipt,
    Standing,
    VerificationResult,
)


def _subset(required: Mapping[str, Any], observed: Mapping[str, Any]) -> bool:
    for key, expected in required.items():
        if key not in observed:
            return False
        actual = observed[key]
        if isinstance(expected, Mapping):
            if not isinstance(actual, Mapping) or not _subset(expected, actual):
                return False
        elif actual != expected:
            return False
    return True


@dataclass(frozen=True)
class HarnessAction:
    """An action intent. It never carries execution authority by itself."""

    capability: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str = field(default_factory=lambda: uuid4().hex)
    expected_after: Mapping[str, Any] | None = None

    def copied_payload(self) -> dict[str, Any]:
        return deepcopy(dict(self.payload))


@dataclass(frozen=True)
class Stage:
    actions: tuple[HarnessAction, ...] = ()


@dataclass(frozen=True)
class ContractRule:
    capability: str
    effect: Literal["allow", "deny", "rewrite"] = "allow"
    required_state: Mapping[str, Any] = field(default_factory=dict)
    rewrite_capability: str | None = None
    payload_overrides: Mapping[str, Any] = field(default_factory=dict)
    max_consecutive: int | None = None
    reason: str = "CONTRACT_RULE"
    feedback: str | None = None

    def __post_init__(self) -> None:
        if self.effect == "rewrite" and not self.rewrite_capability:
            raise ValueError("CONTRACT_REWRITE_REQUIRES_CAPABILITY")
        if self.effect != "rewrite" and self.rewrite_capability is not None:
            raise ValueError("CONTRACT_REWRITE_CAPABILITY_WITHOUT_REWRITE")
        if self.max_consecutive is not None and self.max_consecutive < 1:
            raise ValueError("CONTRACT_MAX_CONSECUTIVE_MUST_BE_POSITIVE")


@dataclass(frozen=True)
class Contract:
    rules: tuple[ContractRule, ...] = ()
    hide_observation_keys: frozenset[str] = frozenset()


@dataclass(frozen=True)
class HarnessSpec:
    stages: tuple[Stage, ...] = ()
    contracts: tuple[Contract, ...] = ()
    identifier: str = field(default_factory=lambda: f"urn:gymact:envharness:{uuid4().hex}")


@dataclass(frozen=True)
class TaskSpec:
    provider: str
    scenario: str | None = None
    config: Mapping[str, Any] = field(default_factory=dict)
    goal: Mapping[str, Any] = field(default_factory=dict)
    harness: HarnessSpec = field(default_factory=HarnessSpec)


@dataclass(frozen=True)
class ContractDecision:
    admitted: bool
    action: HarnessAction
    standing: Standing
    reason: str
    feedback: tuple[str, ...] = ()
    evidence_digest: str = ""


@dataclass(frozen=True)
class HarnessResetResult:
    accepted: bool
    standing: Standing
    materialization: MaterializationResult
    stage_results: tuple[ActuationResult, ...] = ()
    stage_verifications: tuple[VerificationResult, ...] = ()
    rollback_receipt: Receipt | None = None
    reason: str | None = None


@dataclass(frozen=True)
class HarnessStepResult:
    accepted: bool
    standing: Standing
    action: HarnessAction
    observation: Mapping[str, Any]
    actuation: ActuationResult | None = None
    read_result: Mapping[str, Any] | None = None
    contract_decision: ContractDecision | None = None
    reason: str | None = None


class HarnessSession:
    """Paper-like reset/step facade over one real GymAct episode."""

    def __init__(
        self,
        runtime: GymAct,
        task: TaskSpec,
        *,
        authority_ref: str | None = None,
        principal: str | None = None,
    ) -> None:
        self.runtime = runtime
        self.task = task
        self.authority_ref = authority_ref
        self.principal = principal
        self.episode_id: str | None = None
        self._history: list[HarnessAction] = []
        self._feedback: list[str] = []

    @property
    def history(self) -> tuple[HarnessAction, ...]:
        return tuple(self._history)

    @property
    def feedback(self) -> tuple[str, ...]:
        return tuple(self._feedback)

    def _episode(self) -> str:
        if self.episode_id is None:
            raise RuntimeError("ENVHARNESS_NOT_RESET")
        return self.episode_id

    def _capability(self, capability_ref: str) -> Capability | None:
        return next(
            (
                cap
                for cap in self.runtime.capabilities(self._episode())
                if cap.iri == capability_ref
            ),
            None,
        )

    async def _rollback(self, checkpoint: Mapping[str, Any]) -> Receipt:
        return await self.runtime.restore(
            self._episode(),
            deepcopy(dict(checkpoint)),
            authority_ref=self.authority_ref,
        )

    async def reset(self) -> HarnessResetResult:
        """Materialize then transactionally apply reset-time Stage actions."""
        if self.episode_id is not None:
            receipt = await self.teardown()
            if receipt.standing not in {Standing.ALIVE, Standing.PARTIAL_ALIVE}:
                raise RuntimeError(f"ENVHARNESS_PRIOR_TEARDOWN_{receipt.standing}")

        materialization = await self.runtime.materialize(
            MaterializationIntent(
                provider=self.task.provider,
                scenario=self.task.scenario,
                config=deepcopy(dict(self.task.config)),
                authority_ref=self.authority_ref,
                principal=self.principal,
                idempotency_key=uuid4().hex,
            )
        )
        if not materialization.accepted or materialization.episode is None:
            return HarnessResetResult(
                accepted=False,
                standing=materialization.standing,
                materialization=materialization,
                reason=materialization.receipt.reason,
            )

        self.episode_id = materialization.episode.episode_id
        self._history.clear()
        self._feedback.clear()
        baseline = await self.runtime.checkpoint(self.episode_id)
        results: list[ActuationResult] = []
        verifications: list[VerificationResult] = []

        for stage in self.task.harness.stages:
            for action in stage.actions:
                capability = self._capability(action.capability)
                if capability is None or capability.consequence is not Consequence.DO:
                    return HarnessResetResult(
                        accepted=False,
                        standing=Standing.REFUSED,
                        materialization=materialization,
                        stage_results=tuple(results),
                        stage_verifications=tuple(verifications),
                        rollback_receipt=await self._rollback(baseline),
                        reason="STAGE_REQUIRES_DO_CAPABILITY",
                    )
                result = await self.runtime.act(
                    ActuationIntent(
                        episode_id=self.episode_id,
                        capability=action.capability,
                        payload=action.copied_payload(),
                        authority_ref=self.authority_ref,
                        principal=self.principal,
                        idempotency_key=action.idempotency_key,
                    )
                )
                results.append(result)
                if not result.accepted:
                    return HarnessResetResult(
                        accepted=False,
                        standing=result.standing,
                        materialization=materialization,
                        stage_results=tuple(results),
                        stage_verifications=tuple(verifications),
                        rollback_receipt=await self._rollback(baseline),
                        reason=result.receipt.reason,
                    )
                if action.expected_after is not None:
                    verified = await self.runtime.verify(
                        self.episode_id,
                        deepcopy(dict(action.expected_after)),
                    )
                    verifications.append(verified)
                    if not verified.passed:
                        return HarnessResetResult(
                            accepted=False,
                            standing=Standing.REFUSED,
                            materialization=materialization,
                            stage_results=tuple(results),
                            stage_verifications=tuple(verifications),
                            rollback_receipt=await self._rollback(baseline),
                            reason="STAGE_POSTCONDITION_FAILED",
                        )

        return HarnessResetResult(
            accepted=True,
            standing=Standing.ALIVE,
            materialization=materialization,
            stage_results=tuple(results),
            stage_verifications=tuple(verifications),
        )

    async def raw_observe(self) -> Observation:
        return await self.runtime.observe(self._episode())

    async def observe(self) -> dict[str, Any]:
        state = deepcopy((await self.raw_observe()).state)
        for contract in self.task.harness.contracts:
            for key in contract.hide_observation_keys:
                state.pop(key, None)
        if self._feedback:
            state["_envharness_feedback"] = tuple(self._feedback)
        return state

    def _consecutive_count(self, capability: str) -> int:
        count = 0
        for action in reversed(self._history):
            if action.capability != capability:
                break
            count += 1
        return count

    def _decision_digest(
        self,
        action: HarnessAction,
        raw: Observation,
        admitted: bool,
        reason: str,
        feedback: Sequence[str],
    ) -> str:
        return digest(
            {
                "harness": self.task.harness.identifier,
                "action": {
                    "capability": action.capability,
                    "payload": action.copied_payload(),
                    "idempotency_key": action.idempotency_key,
                },
                "raw_state_digest": raw.state_digest,
                "history_length": len(self._history),
                "admitted": admitted,
                "reason": reason,
                "feedback": list(feedback),
            }
        )

    async def admit(self, action: HarnessAction) -> ContractDecision:
        raw = await self.raw_observe()
        current = action
        feedback: list[str] = []
        reason = "CONTRACT_ADMITTED"
        for contract in self.task.harness.contracts:
            for rule in contract.rules:
                if rule.capability != current.capability:
                    continue
                if rule.required_state and not _subset(rule.required_state, raw.state):
                    continue
                if (
                    rule.max_consecutive is not None
                    and self._consecutive_count(current.capability) < rule.max_consecutive
                ):
                    continue
                if rule.feedback:
                    feedback.append(rule.feedback)
                reason = rule.reason
                if rule.effect == "deny":
                    return ContractDecision(
                        admitted=False,
                        action=current,
                        standing=Standing.REFUSED,
                        reason=reason,
                        feedback=tuple(feedback),
                        evidence_digest=self._decision_digest(
                            current, raw, False, reason, feedback
                        ),
                    )
                payload = current.copied_payload()
                payload.update(deepcopy(dict(rule.payload_overrides)))
                current = HarnessAction(
                    capability=(
                        rule.rewrite_capability if rule.effect == "rewrite" else current.capability
                    )
                    or current.capability,
                    payload=payload,
                    idempotency_key=current.idempotency_key,
                    expected_after=current.expected_after,
                )
        return ContractDecision(
            admitted=True,
            action=current,
            standing=Standing.ALIVE,
            reason=reason,
            feedback=tuple(feedback),
            evidence_digest=self._decision_digest(current, raw, True, reason, feedback),
        )

    async def step(self, action: HarnessAction) -> HarnessStepResult:
        decision = await self.admit(action)
        self._feedback.extend(decision.feedback)
        if not decision.admitted:
            return HarnessStepResult(
                accepted=False,
                standing=decision.standing,
                action=decision.action,
                observation=await self.observe(),
                contract_decision=decision,
                reason=decision.reason,
            )
        capability = self._capability(decision.action.capability)
        if capability is None:
            return HarnessStepResult(
                accepted=False,
                standing=Standing.UNSUPPORTED,
                action=decision.action,
                observation=await self.observe(),
                contract_decision=decision,
                reason="UNKNOWN_CAPABILITY",
            )
        if capability.consequence is Consequence.READ:
            read_result = await self.runtime.read(
                self._episode(),
                decision.action.capability,
                decision.action.copied_payload(),
            )
            self._history.append(decision.action)
            return HarnessStepResult(
                accepted=True,
                standing=Standing.ALIVE,
                action=decision.action,
                observation=await self.observe(),
                read_result=deepcopy(read_result),
                contract_decision=decision,
            )
        actuation = await self.runtime.act(
            ActuationIntent(
                episode_id=self._episode(),
                capability=decision.action.capability,
                payload=decision.action.copied_payload(),
                authority_ref=self.authority_ref,
                principal=self.principal,
                idempotency_key=decision.action.idempotency_key,
            )
        )
        if actuation.accepted:
            self._history.append(decision.action)
        return HarnessStepResult(
            accepted=actuation.accepted,
            standing=actuation.standing,
            action=decision.action,
            observation=await self.observe(),
            actuation=actuation,
            contract_decision=decision,
            reason=actuation.receipt.reason,
        )

    async def verify(self, expected: Mapping[str, Any] | None = None) -> VerificationResult:
        return await self.runtime.verify(
            self._episode(),
            deepcopy(dict(self.task.goal if expected is None else expected)),
        )

    async def checkpoint(self) -> dict[str, Any]:
        return await self.runtime.checkpoint(self._episode())

    async def restore(self, checkpoint: Mapping[str, Any]) -> Receipt:
        return await self._rollback(checkpoint)

    async def teardown(self) -> Receipt:
        receipt = await self.runtime.teardown(
            self._episode(),
            authority_ref=self.authority_ref,
        )
        if receipt.standing in {Standing.ALIVE, Standing.PARTIAL_ALIVE}:
            self.episode_id = None
        return receipt


@dataclass(frozen=True)
class ChainAdvanceResult:
    accepted: bool
    standing: Standing
    leg_index: int
    verification: VerificationResult
    complete: bool
    next_reset: HarnessResetResult | None = None
    reason: str | None = None


class ChainSession:
    """Serial Chain; success is the conjunction of original leg verifiers."""

    def __init__(
        self,
        runtime: GymAct,
        tasks: Sequence[TaskSpec],
        *,
        authority_ref: str | None = None,
        principal: str | None = None,
    ) -> None:
        if not tasks:
            raise ValueError("CHAIN_REQUIRES_AT_LEAST_ONE_TASK")
        self.runtime = runtime
        self.tasks = tuple(tasks)
        self.authority_ref = authority_ref
        self.principal = principal
        self.leg_index = 0
        self.current: HarnessSession | None = None
        self._verifications: list[VerificationResult] = []

    @property
    def verifications(self) -> tuple[VerificationResult, ...]:
        return tuple(self._verifications)

    @property
    def complete(self) -> bool:
        return len(self._verifications) == len(self.tasks) and all(
            result.passed for result in self._verifications
        )

    async def reset(self) -> HarnessResetResult:
        if self.current is not None and self.current.episode_id is not None:
            await self.current.teardown()
        self.leg_index = 0
        self._verifications.clear()
        self.current = HarnessSession(
            self.runtime,
            self.tasks[0],
            authority_ref=self.authority_ref,
            principal=self.principal,
        )
        return await self.current.reset()

    async def step(self, action: HarnessAction) -> HarnessStepResult:
        if self.current is None:
            raise RuntimeError("CHAIN_NOT_RESET")
        return await self.current.step(action)

    async def observe(self) -> dict[str, Any]:
        if self.current is None:
            raise RuntimeError("CHAIN_NOT_RESET")
        return await self.current.observe()

    async def advance(self) -> ChainAdvanceResult:
        if self.current is None:
            raise RuntimeError("CHAIN_NOT_RESET")
        verification = await self.current.verify()
        if not verification.passed:
            return ChainAdvanceResult(
                False,
                Standing.REFUSED,
                self.leg_index,
                verification,
                False,
                reason="CHAIN_LEG_NOT_VERIFIED",
            )
        self._verifications.append(verification)
        finished = self.leg_index
        if self.leg_index == len(self.tasks) - 1:
            return ChainAdvanceResult(True, Standing.ALIVE, finished, verification, True)
        teardown = await self.current.teardown()
        if teardown.standing not in {Standing.ALIVE, Standing.PARTIAL_ALIVE}:
            return ChainAdvanceResult(
                False,
                teardown.standing,
                finished,
                verification,
                False,
                reason=teardown.reason or "CHAIN_LEG_TEARDOWN_FAILED",
            )
        self.leg_index += 1
        self.current = HarnessSession(
            self.runtime,
            self.tasks[self.leg_index],
            authority_ref=self.authority_ref,
            principal=self.principal,
        )
        next_reset = await self.current.reset()
        return ChainAdvanceResult(
            next_reset.accepted,
            next_reset.standing,
            finished,
            verification,
            False,
            next_reset=next_reset,
            reason=next_reset.reason,
        )
