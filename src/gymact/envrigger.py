"""Black-box EnvRigger loop for synthesizing and validating EnvHarness specs.

The paper's Observe -> Diagnose -> Write -> Validate cycle is represented explicitly.
Synthesizers return declarative :class:`gymact.envharness.HarnessSpec` values; generated
Python is never imported or executed. All rollout actions still flow through
``HarnessSession.step`` and therefore through GymAct's authority/Receipt boundary.
"""

from __future__ import annotations

import inspect
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from statistics import fmean
from typing import Any, Protocol

from gymact.envharness import (
    Contract,
    ContractRule,
    HarnessAction,
    HarnessSession,
    HarnessSpec,
    TaskSpec,
)
from gymact.models import Capability, Standing


class BlackBoxPolicy(Protocol):
    """Policy observed only through inputs and action outputs."""

    def __call__(
        self,
        observation: dict[str, Any],
        capabilities: tuple[Capability, ...],
    ) -> HarnessAction | Awaitable[HarnessAction | None] | None: ...


@dataclass(frozen=True)
class TrajectoryStep:
    index: int
    observation: dict[str, Any]
    action: HarnessAction | None
    accepted: bool | None = None
    standing: Standing | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Rollout:
    steps: tuple[TrajectoryStep, ...]
    solved: bool
    reset_standing: Standing
    verification_id: str | None = None


@dataclass(frozen=True)
class Diagnosis:
    rollout_count: int
    success_rate: float
    mean_steps: float
    repeated_capability: str | None
    max_consecutive_repeat: int
    failure_reasons: tuple[tuple[str, int], ...]
    signal: str


class HarnessSynthesizer(Protocol):
    """Manufacture one declarative candidate from rollout evidence."""

    def propose(
        self,
        *,
        task: TaskSpec,
        diagnosis: Diagnosis,
        rollouts: tuple[Rollout, ...],
        revision: int,
        previous: HarnessSpec,
    ) -> HarnessSpec | None: ...


@dataclass(frozen=True)
class ValidationMetrics:
    rollouts: int
    solved: int
    success_rate: float
    mean_steps: float
    fresh_rollouts: bool


@dataclass(frozen=True)
class CandidateEvaluation:
    revision: int
    harness: HarnessSpec
    diagnosis: Diagnosis
    validation: ValidationMetrics
    disposition: str
    reason: str


@dataclass(frozen=True)
class EnvRiggerResult:
    standing: Standing
    baseline: tuple[Rollout, ...]
    baseline_diagnosis: Diagnosis
    evaluations: tuple[CandidateEvaluation, ...]
    accepted_harness: HarnessSpec | None
    reason: str


@dataclass(frozen=True)
class EnvRiggerConfig:
    baseline_rollouts: int = 3
    validation_rollouts: int = 5
    max_steps: int = 32
    revision_budget: int = 3
    min_solvable_success_rate: float = 0.2
    max_easy_success_rate: float = 0.8

    def __post_init__(self) -> None:
        if self.baseline_rollouts < 1 or self.validation_rollouts < 1:
            raise ValueError("ENVRIGGER_REQUIRES_ROLLOUTS")
        if self.max_steps < 1 or self.revision_budget < 1:
            raise ValueError("ENVRIGGER_POSITIVE_BOUNDS_REQUIRED")
        if not 0.0 <= self.min_solvable_success_rate <= 1.0:
            raise ValueError("ENVRIGGER_INVALID_MIN_SUCCESS_RATE")
        if not 0.0 <= self.max_easy_success_rate <= 1.0:
            raise ValueError("ENVRIGGER_INVALID_MAX_SUCCESS_RATE")
        if self.min_solvable_success_rate > self.max_easy_success_rate:
            raise ValueError("ENVRIGGER_SUCCESS_BAND_INVERTED")


SessionFactory = Callable[[TaskSpec], HarnessSession]


def _max_consecutive_capability(rollouts: Sequence[Rollout]) -> tuple[str | None, int]:
    best_capability: str | None = None
    best_count = 0
    for rollout in rollouts:
        prior: str | None = None
        count = 0
        for step in rollout.steps:
            capability = step.action.capability if step.action is not None else None
            if capability is not None and capability == prior:
                count += 1
            elif capability is not None:
                prior = capability
                count = 1
            else:
                prior = None
                count = 0
            if count > best_count:
                best_capability = capability
                best_count = count
    return best_capability, best_count


def diagnose_rollouts(rollouts: Sequence[Rollout]) -> Diagnosis:
    """Deterministic black-box diagnosis from trajectories only."""
    if not rollouts:
        raise ValueError("ENVRIGGER_DIAGNOSIS_REQUIRES_ROLLOUTS")
    success_rate = sum(1 for rollout in rollouts if rollout.solved) / len(rollouts)
    repeated_capability, repeat_count = _max_consecutive_capability(rollouts)
    reasons = Counter(
        step.reason for rollout in rollouts for step in rollout.steps if step.reason is not None
    )
    if success_rate == 0.0:
        signal = "UNSOLVABLE_OBSERVED"
    elif success_rate == 1.0:
        signal = "TOO_EASY_OBSERVED"
    else:
        signal = "MIXED_SUCCESS_OBSERVED"
    if repeat_count >= 3:
        signal = f"{signal};ACTION_LOOP_OBSERVED"
    return Diagnosis(
        rollout_count=len(rollouts),
        success_rate=success_rate,
        mean_steps=fmean(len(rollout.steps) for rollout in rollouts),
        repeated_capability=repeated_capability,
        max_consecutive_repeat=repeat_count,
        failure_reasons=tuple(sorted(reasons.items())),
        signal=signal,
    )


class LoopGuardSynthesizer:
    """Deterministic reference Write stage for one diagnosis class.

    When black-box traces exhibit a >=3-step consecutive action loop, add a Contract rule
    that permits the first two consecutive actions and refuses the third with feedback.
    This is intentionally narrow: no domain state mutation is guessed from trajectories.
    More capable LLM/solver synthesizers implement ``HarnessSynthesizer`` and still return
    the same data-only ``HarnessSpec``.
    """

    def propose(
        self,
        *,
        task: TaskSpec,
        diagnosis: Diagnosis,
        rollouts: tuple[Rollout, ...],
        revision: int,
        previous: HarnessSpec,
    ) -> HarnessSpec | None:
        del task, rollouts
        capability = diagnosis.repeated_capability
        if capability is None or diagnosis.max_consecutive_repeat < 3:
            return None
        rule = ContractRule(
            capability=capability,
            effect="deny",
            max_consecutive=2,
            reason="ENVRIGGER_ACTION_LOOP_GUARD",
            feedback="Repeated action blocked; select a different capability.",
        )
        guard = Contract(rules=(rule,))
        return replace(
            previous,
            contracts=(*previous.contracts, guard),
            identifier=f"{previous.identifier}:r{revision}",
        )


class EnvRigger:
    """Bounded Observe -> Diagnose -> Write -> Validate harness search."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        policy: BlackBoxPolicy,
        synthesizer: HarnessSynthesizer | None = None,
        config: EnvRiggerConfig | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.policy = policy
        self.synthesizer = synthesizer or LoopGuardSynthesizer()
        self.config = config or EnvRiggerConfig()

    async def _policy_action(
        self,
        observation: dict[str, Any],
        capabilities: tuple[Capability, ...],
    ) -> HarnessAction | None:
        result = self.policy(observation, capabilities)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _rollout(self, task: TaskSpec) -> Rollout:
        """Run one fresh materialization; no episode is reused across validations."""
        session = self.session_factory(task)
        reset = await session.reset()
        if not reset.accepted or session.episode_id is None:
            return Rollout(steps=(), solved=False, reset_standing=reset.standing)

        steps: list[TrajectoryStep] = []
        verification_id: str | None = None
        solved = False
        try:
            for index in range(self.config.max_steps):
                verification = await session.verify()
                verification_id = verification.verification_id
                if verification.passed:
                    solved = True
                    break
                observation = await session.observe()
                capabilities = session.runtime.capabilities(session.episode_id)
                action = await self._policy_action(observation, capabilities)
                if action is None:
                    steps.append(TrajectoryStep(index=index, observation=observation, action=None))
                    break
                result = await session.step(action)
                steps.append(
                    TrajectoryStep(
                        index=index,
                        observation=observation,
                        action=result.action,
                        accepted=result.accepted,
                        standing=result.standing,
                        reason=result.reason,
                    )
                )
            if not solved:
                verification = await session.verify()
                verification_id = verification.verification_id
                solved = verification.passed
        finally:
            await session.teardown()

        return Rollout(
            steps=tuple(steps),
            solved=solved,
            reset_standing=reset.standing,
            verification_id=verification_id,
        )

    async def _rollouts(self, task: TaskSpec, count: int) -> tuple[Rollout, ...]:
        return tuple([await self._rollout(task) for _ in range(count)])

    @staticmethod
    def _metrics(rollouts: tuple[Rollout, ...]) -> ValidationMetrics:
        solved = sum(1 for rollout in rollouts if rollout.solved)
        return ValidationMetrics(
            rollouts=len(rollouts),
            solved=solved,
            success_rate=solved / len(rollouts),
            mean_steps=fmean(len(rollout.steps) for rollout in rollouts),
            fresh_rollouts=True,
        )

    def _classify(self, metrics: ValidationMetrics) -> tuple[str, str]:
        if metrics.success_rate < self.config.min_solvable_success_rate:
            return "REFINE", "CANDIDATE_NOT_SOLVABLE_ENOUGH"
        if metrics.success_rate > self.config.max_easy_success_rate:
            return "REFINE", "CANDIDATE_NOT_CHALLENGING_ENOUGH"
        return "ACCEPT", "CANDIDATE_SOLVABLE_AND_CHALLENGING"

    async def run(self, task: TaskSpec) -> EnvRiggerResult:
        """Execute the complete bounded EnvRigger loop against black-box rollouts."""
        observed_baseline = await self._rollouts(task, self.config.baseline_rollouts)
        baseline_diagnosis = diagnose_rollouts(observed_baseline)
        working_rollouts = observed_baseline
        diagnosis = baseline_diagnosis
        previous = task.harness
        evaluations: list[CandidateEvaluation] = []

        for revision in range(1, self.config.revision_budget + 1):
            candidate = self.synthesizer.propose(
                task=task,
                diagnosis=diagnosis,
                rollouts=working_rollouts,
                revision=revision,
                previous=previous,
            )
            if candidate is None:
                return EnvRiggerResult(
                    standing=Standing.UNSUPPORTED,
                    baseline=observed_baseline,
                    baseline_diagnosis=baseline_diagnosis,
                    evaluations=tuple(evaluations),
                    accepted_harness=None,
                    reason="SYNTHESIZER_HAS_NO_LAWFUL_CANDIDATE",
                )

            candidate_task = replace(task, harness=candidate)
            validation_rollouts = await self._rollouts(
                candidate_task,
                self.config.validation_rollouts,
            )
            metrics = self._metrics(validation_rollouts)
            disposition, reason = self._classify(metrics)
            evaluation = CandidateEvaluation(
                revision=revision,
                harness=candidate,
                diagnosis=diagnose_rollouts(validation_rollouts),
                validation=metrics,
                disposition=disposition,
                reason=reason,
            )
            evaluations.append(evaluation)
            if disposition == "ACCEPT":
                return EnvRiggerResult(
                    standing=Standing.ALIVE,
                    baseline=observed_baseline,
                    baseline_diagnosis=baseline_diagnosis,
                    evaluations=tuple(evaluations),
                    accepted_harness=candidate,
                    reason=reason,
                )

            previous = candidate
            working_rollouts = validation_rollouts
            diagnosis = evaluation.diagnosis

        return EnvRiggerResult(
            standing=Standing.REFUSED,
            baseline=observed_baseline,
            baseline_diagnosis=baseline_diagnosis,
            evaluations=tuple(evaluations),
            accepted_harness=None,
            reason="ENVRIGGER_REVISION_BUDGET_EXHAUSTED",
        )
