"""Executable lab experiments for fault injection, self-play, VCT, and cognition compile-out."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import StrEnum

from pydantic import Field

from gymact.models import FrozenModel, Standing


class FaultKind(StrEnum):
    TIMEOUT = "TIMEOUT"
    LOST_ACK = "LOST_ACK"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    PARTIAL_EFFECT = "PARTIAL_EFFECT"
    AUTHORITY_EXPIRY = "AUTHORITY_EXPIRY"
    RATE_LIMIT = "RATE_LIMIT"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    REORDERED_EVENT = "REORDERED_EVENT"
    DEPENDENCY_OUTAGE = "DEPENDENCY_OUTAGE"


class FaultPlan(FrozenModel):
    fault: FaultKind
    occurrence: int = Field(default=1, ge=1)
    operation_ref: str = Field(min_length=1)
    bounded: bool = True


class FaultDecision(FrozenModel):
    inject: bool
    fault: FaultKind | None = None
    occurrence: int
    reason: str


class FaultInjector:
    """Deterministic lab-only fault selector; it never owns the external operation."""

    def __init__(self, plans: Iterable[FaultPlan]) -> None:
        self._plans = tuple(plans)
        if any(not plan.bounded for plan in self._plans):
            raise ValueError("UNBOUNDED_FAULT_INJECTION_REFUSED")
        self._counts: dict[str, int] = {}

    def decide(self, operation_ref: str) -> FaultDecision:
        occurrence = self._counts.get(operation_ref, 0) + 1
        self._counts[operation_ref] = occurrence
        for plan in self._plans:
            if plan.operation_ref == operation_ref and plan.occurrence == occurrence:
                return FaultDecision(
                    inject=True,
                    fault=plan.fault,
                    occurrence=occurrence,
                    reason="BOUNDED_FAULT_INJECTED",
                )
        return FaultDecision(
            inject=False,
            occurrence=occurrence,
            reason="NO_FAULT_FOR_OCCURRENCE",
        )


class SelfPlayCase(FrozenModel):
    case_id: str = Field(min_length=1)
    expected_disposition: str = Field(min_length=1)
    safety_critical: bool = False


class SelfPlayObservation(FrozenModel):
    case_id: str
    expected_disposition: str
    observed_disposition: str
    passed: bool
    safety_critical: bool


class SelfPlayReport(FrozenModel):
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    incorrect_safety_crowns: int = Field(ge=0)
    observations: tuple[SelfPlayObservation, ...]

    @property
    def crown_safe(self) -> bool:
        return self.incorrect_safety_crowns == 0


def run_self_play(
    cases: Iterable[SelfPlayCase],
    evaluator: Callable[[SelfPlayCase], str],
) -> SelfPlayReport:
    observations: list[SelfPlayObservation] = []
    incorrect_safety_crowns = 0
    for case in cases:
        observed = evaluator(case)
        passed = observed == case.expected_disposition
        if case.safety_critical and observed == Standing.ALIVE.value and not passed:
            incorrect_safety_crowns += 1
        observations.append(
            SelfPlayObservation(
                case_id=case.case_id,
                expected_disposition=case.expected_disposition,
                observed_disposition=observed,
                passed=passed,
                safety_critical=case.safety_critical,
            )
        )
    passed_count = sum(item.passed for item in observations)
    return SelfPlayReport(
        total=len(observations),
        passed=passed_count,
        failed=len(observations) - passed_count,
        incorrect_safety_crowns=incorrect_safety_crowns,
        observations=tuple(observations),
    )


class TransitionEconomics(FrozenModel):
    repetitions: int = Field(gt=0)
    verified_transitions: int = Field(ge=0)
    wall_time_s: float = Field(gt=0)
    monetary_cost: float = Field(gt=0)
    human_intervention_factor: float = Field(gt=0)
    model_tokens: int = Field(ge=0)

    @property
    def vct(self) -> float:
        return self.verified_transitions / (
            self.wall_time_s * self.monetary_cost * self.human_intervention_factor
        )


class AntiAgentPoint(FrozenModel):
    repetitions: int = Field(gt=0)
    frontier: TransitionEconomics
    gymact: TransitionEconomics


class AntiAgentReport(FrozenModel):
    points: tuple[AntiAgentPoint, ...]
    crossover_repetitions: int | None = None
    gymact_lower_marginal_cost: bool


def anti_agent_benchmark(points: Iterable[AntiAgentPoint]) -> AntiAgentReport:
    ordered = tuple(sorted(points, key=lambda item: item.repetitions))
    if not ordered:
        raise ValueError("ANTI_AGENT_POINTS_REQUIRED")
    crossover = next(
        (
            point.repetitions
            for point in ordered
            if point.gymact.monetary_cost < point.frontier.monetary_cost
        ),
        None,
    )
    lower_marginal = False
    if len(ordered) >= 2:
        first, last = ordered[0], ordered[-1]
        frontier_slope = (
            last.frontier.monetary_cost - first.frontier.monetary_cost
        ) / (last.repetitions - first.repetitions)
        gymact_slope = (
            last.gymact.monetary_cost - first.gymact.monetary_cost
        ) / (last.repetitions - first.repetitions)
        lower_marginal = gymact_slope < frontier_slope
    return AntiAgentReport(
        points=ordered,
        crossover_repetitions=crossover,
        gymact_lower_marginal_cost=lower_marginal,
    )


class IntelligenceRun(FrozenModel):
    regime: str
    model_tokens: int = Field(ge=0)
    monetary_cost: float = Field(ge=0)
    wall_time_s: float = Field(ge=0)
    authority_policy_ref: str = Field(min_length=1)
    verifier_ref: str = Field(min_length=1)
    verified: bool
    receipt_ref: str = Field(min_length=1)


class CompileOutReport(FrozenModel):
    cold: IntelligenceRun
    hot: IntelligenceRun
    compiled_out: bool
    authority_preserved: bool
    verification_preserved: bool
    reason: str


def evaluate_compile_out(cold: IntelligenceRun, hot: IntelligenceRun) -> CompileOutReport:
    authority_preserved = cold.authority_policy_ref == hot.authority_policy_ref
    verification_preserved = cold.verifier_ref == hot.verifier_ref and cold.verified and hot.verified
    compiled = (
        cold.model_tokens > 0
        and hot.model_tokens == 0
        and hot.monetary_cost < cold.monetary_cost
        and hot.wall_time_s <= cold.wall_time_s
        and authority_preserved
        and verification_preserved
    )
    return CompileOutReport(
        cold=cold,
        hot=hot,
        compiled_out=compiled,
        authority_preserved=authority_preserved,
        verification_preserved=verification_preserved,
        reason="COGNITION_COMPILED_OUT" if compiled else "COMPILE_OUT_NOT_PROVEN",
    )
