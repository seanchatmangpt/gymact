"""Typed three-phase temperament-engineering workflow.

The paper's design object is a distribution of behavioral conditions, not an
individual controller. This module makes that workflow executable while
preserving GymAct's existing authority boundary:

1. mission criteria declare which behavioral axes matter;
2. a bounded distribution is manufactured over those axes;
3. reaction norms adapt that distribution to environmental cues.

All outputs are candidate policy populations. No object here can carry or grant
execution authority.
"""

from __future__ import annotations

from enum import StrEnum
from math import sqrt
from typing import Self

from pydantic import Field, model_validator

from gymact.models import FrozenModel
from gymact.policy_ecology import (
    ConditionAxis,
    PolicyPhenotype,
    PolicyPopulation,
    PopulationDiversity,
    PopulationKind,
    ReactionNorm,
    StrategicCondition,
    WeightedPhenotype,
    _normalized_axis_id,
    population_diversity,
)
from gymact.policy_ecology import _refuse_axis_pairs as _policy_refuse_axis_pairs


def _refuse_axis_pairs(
    pairs: tuple[tuple[str, float], ...],
    *,
    duplicate: str,
    non_finite: str,
) -> None:
    # One admission path for every axis-naming surface: empty, non-ASCII and
    # authority-encoding axis ids are refused exactly as ConditionAxis does.
    _policy_refuse_axis_pairs(pairs, duplicate, non_finite)


class ControlTopology(StrEnum):
    CENTRALIZED = "centralized"
    DECENTRALIZED = "decentralized"


class DesignMode(StrEnum):
    ONLINE_PLANNER_OUTPUT = "online_planner_output"
    OFFLINE_ANTICIPATORY = "offline_anticipatory"


class DistributionShape(StrEnum):
    POINT = "point"
    UNIFORM = "uniform"
    BIMODAL = "bimodal"


class MissionCriterion(FrozenModel):
    criterion_id: str = Field(min_length=1)
    axis_weights: tuple[tuple[str, float], ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def criterion_contract(self) -> Self:
        _refuse_axis_pairs(
            self.axis_weights,
            duplicate="DUPLICATE_CRITERION_AXIS",
            non_finite="NON_FINITE_AXIS_RELEVANCE",
        )
        if any(weight < 0.0 for _, weight in self.axis_weights):
            raise ValueError("REFUSED:NEGATIVE_AXIS_RELEVANCE")
        if not any(weight > 0.0 for _, weight in self.axis_weights):
            raise ValueError("REFUSED:CRITERION_REQUIRES_POSITIVE_AXIS_RELEVANCE")
        return self


class AxisTarget(FrozenModel):
    axis_id: str = Field(min_length=1)
    mean: float = Field(ge=0.0, le=1.0)
    spread: float = Field(default=0.0, ge=0.0, le=0.5)
    shape: DistributionShape = DistributionShape.POINT
    cue_slope: float = Field(default=0.0, allow_inf_nan=False)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def target_contract(self) -> Self:
        if self.shape is DistributionShape.POINT and self.spread != 0.0:
            raise ValueError("REFUSED:POINT_DISTRIBUTION_REQUIRES_ZERO_SPREAD")
        if self.mean - self.spread < 0.0 or self.mean + self.spread > 1.0:
            # A clamped interval silently moves the realized mean off target;
            # refuse the design instead of manufacturing a biased population.
            raise ValueError(f"REFUSED:TARGET_INTERVAL_OUTSIDE_UNIT_RANGE:{self.axis_id}")
        return self


class PlatformTrait(FrozenModel):
    trait_id: str = Field(min_length=1)
    value: float = Field(allow_inf_nan=False)
    axis_couplings: tuple[tuple[str, float], ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def trait_contract(self) -> Self:
        _refuse_axis_pairs(
            self.axis_couplings,
            duplicate="DUPLICATE_PLATFORM_AXIS_COUPLING",
            non_finite="NON_FINITE_PLATFORM_AXIS_COUPLING",
        )
        return self


class TemperamentDesignPlan(FrozenModel):
    mission_id: str = Field(min_length=1)
    topology: ControlTopology
    mode: DesignMode
    criteria: tuple[MissionCriterion, ...] = Field(min_length=1)
    targets: tuple[AxisTarget, ...] = Field(min_length=1)
    reaction_norm: ReactionNorm | None = None
    platform_traits: tuple[PlatformTrait, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def design_contract(self) -> Self:
        target_ids = [target.axis_id for target in self.targets]
        if len({_normalized_axis_id(axis) for axis in target_ids}) != len(target_ids):
            raise ValueError("REFUSED:DUPLICATE_TEMPERAMENT_TARGET")
        if (
            self.topology is ControlTopology.DECENTRALIZED
            and self.mode is DesignMode.ONLINE_PLANNER_OUTPUT
        ):
            raise ValueError("REFUSED:DECENTRALIZED_SWARM_REQUIRES_ANTICIPATORY_DESIGN")
        for target in self.targets:
            ConditionAxis(axis_id=target.axis_id)
        # Phase 1 -> Phase 2 binding: every manufactured axis must be one the
        # mission criteria declare relevant (positive weight in some criterion).
        relevant = {
            _normalized_axis_id(axis)
            for criterion in self.criteria
            for axis, weight in criterion.axis_weights
            if weight > 0.0
        }
        for target in self.targets:
            if _normalized_axis_id(target.axis_id) not in relevant:
                raise ValueError(f"REFUSED:TARGET_AXIS_WITHOUT_MISSION_RELEVANCE:{target.axis_id}")
        target_set = set(target_ids)
        unknown_reaction_axes = {
            axis
            for axis, _ in (self.reaction_norm.slopes if self.reaction_norm else ())
            if axis not in target_set
        }
        if unknown_reaction_axes:
            axis = sorted(unknown_reaction_axes)[0]
            raise ValueError(f"REFUSED:REACTION_NORM_OUTSIDE_DESIGN:{axis}")
        for trait in self.platform_traits:
            unknown = {axis for axis, _ in trait.axis_couplings if axis not in target_set}
            if unknown:
                axis = sorted(unknown)[0]
                raise ValueError(f"REFUSED:PLATFORM_COUPLING_OUTSIDE_DESIGN:{axis}")
        return self


class AxisRelevance(FrozenModel):
    axis_id: str
    score: float = Field(ge=0.0)


class AxisFit(FrozenModel):
    axis_id: str
    target_mean: float
    observed_mean: float
    target_spread: float
    observed_spread: float
    mean_error: float = Field(ge=0.0)
    spread_error: float = Field(ge=0.0)


class DesignEvaluation(FrozenModel):
    axis_fit: tuple[AxisFit, ...]
    mean_absolute_error: float = Field(ge=0.0)
    diversity: PopulationDiversity
    member_count: int = Field(ge=1)


def axis_relevance(criteria: tuple[MissionCriterion, ...]) -> tuple[AxisRelevance, ...]:
    """Aggregate explicit mission-to-axis mappings without inventing semantics."""
    totals: dict[str, float] = {}
    for criterion in criteria:
        for axis_id, weight in criterion.axis_weights:
            totals[axis_id] = totals.get(axis_id, 0.0) + weight
    total = sum(totals.values())
    if total <= 0.0:
        raise ValueError("REFUSED:MISSION_HAS_NO_AXIS_RELEVANCE")
    return tuple(
        AxisRelevance(axis_id=axis_id, score=score / total)
        for axis_id, score in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    )


def _bounded_interval(target: AxisTarget) -> tuple[float, float]:
    # AxisTarget refuses intervals outside [0, 1], so no clamping is needed.
    return target.mean - target.spread, target.mean + target.spread


def _axis_samples(target: AxisTarget, member_count: int) -> tuple[float, ...]:
    if member_count < 1:
        raise ValueError("REFUSED:POPULATION_REQUIRES_MEMBER")
    if target.shape is DistributionShape.POINT:
        return tuple(target.mean for _ in range(member_count))

    low, high = _bounded_interval(target)
    if target.shape is DistributionShape.BIMODAL:
        if member_count == 1:
            return (target.mean,)
        # Symmetric split: n//2 members at each mode; an odd member count puts
        # the middle member at the target mean so the realized mean is exact.
        split = member_count // 2
        return tuple(
            low if index < split else high if index >= member_count - split else target.mean
            for index in range(member_count)
        )

    if member_count == 1:
        return (target.mean,)
    step = (high - low) / (member_count - 1)
    return tuple(low + step * index for index in range(member_count))


def manufacture_population(
    plan: TemperamentDesignPlan,
    *,
    policy_ref: str,
    member_count: int,
) -> PolicyPopulation:
    """Manufacture the planned behavioral distribution as powerless candidates."""
    if not policy_ref.strip():
        raise ValueError("REFUSED:POLICY_REF_REQUIRED")
    samples = {target.axis_id: _axis_samples(target, member_count) for target in plan.targets}

    members: list[WeightedPhenotype] = []
    for index in range(member_count):
        condition = StrategicCondition(
            values=tuple(sorted((axis_id, values[index]) for axis_id, values in samples.items()))
        )
        members.append(
            WeightedPhenotype(
                phenotype=PolicyPhenotype(
                    policy_ref=policy_ref,
                    condition=condition,
                    evidence_refs=plan.evidence_refs,
                ),
                weight=1.0,
            )
        )

    if plan.reaction_norm is not None:
        kind = PopulationKind.ADAPTIVE
    elif member_count == 1 or all(target.spread == 0.0 for target in plan.targets):
        # Every member is the same phenotype: a homogeneous population is one
        # phenotype carrying the whole mass, not N indistinguishable copies
        # (which PolicyPopulation refuses and which would inflate complexity).
        kind = PopulationKind.HOMOGENEOUS
        members = [WeightedPhenotype(phenotype=members[0].phenotype, weight=float(member_count))]
    else:
        kind = PopulationKind.ENGINEERED
    return PolicyPopulation(
        kind=kind,
        members=tuple(members),
        reaction_norm=plan.reaction_norm,
    )


def apply_platform_heterogeneity(
    population: PolicyPopulation,
    plan: TemperamentDesignPlan,
) -> PolicyPopulation:
    """Co-design behavioral and platform heterogeneity through declared couplings."""
    if not plan.platform_traits:
        return population

    target_axes = {target.axis_id for target in plan.targets}
    members: list[WeightedPhenotype] = []
    for member in population.members:
        values = member.phenotype.condition.as_dict()
        for trait in plan.platform_traits:
            for axis_id, coupling in trait.axis_couplings:
                if axis_id not in target_axes:
                    raise ValueError(f"REFUSED:PLATFORM_COUPLING_OUTSIDE_DESIGN:{axis_id}")
                values[axis_id] = min(
                    1.0,
                    max(0.0, values.get(axis_id, 0.0) + trait.value * coupling),
                )
        members.append(
            WeightedPhenotype(
                phenotype=PolicyPhenotype(
                    policy_ref=member.phenotype.policy_ref,
                    condition=StrategicCondition(values=tuple(sorted(values.items()))),
                    evidence_refs=tuple(
                        dict.fromkeys(
                            (
                                *member.phenotype.evidence_refs,
                                *(
                                    ref
                                    for trait in plan.platform_traits
                                    for ref in trait.evidence_refs
                                ),
                            )
                        )
                    ),
                ),
                weight=member.weight,
            )
        )
    return PolicyPopulation(
        kind=population.kind,
        members=tuple(members),
        reaction_norm=population.reaction_norm,
    )


def _weighted_axis_values(
    population: PolicyPopulation,
    axis_id: str,
) -> tuple[tuple[float, float], ...]:
    weights = population.normalized_weights()
    return tuple(
        (member.phenotype.condition.as_dict().get(axis_id, 0.0), weight)
        for member, weight in zip(population.members, weights, strict=True)
    )


def _target_spread(target: AxisTarget, member_count: int) -> float:
    """Population standard deviation of the exact n-member design.

    The target is the discrete distribution manufacture_population realizes,
    not its continuous limit, so a perfect manufacture has zero spread error:
    UNIFORM is an evenly spaced n-point grid, std = w * sqrt((n+1)/(12(n-1)));
    BIMODAL puts n//2 members at each mode (odd n: one at the mean),
    std = (w/2) * sqrt(2*(n//2)/n). Both tend to the continuous values
    w/sqrt(12) and w/2 as n grows.
    """
    low, high = _bounded_interval(target)
    width = high - low
    if target.shape is DistributionShape.POINT or member_count < 2 or width == 0.0:
        return 0.0
    if target.shape is DistributionShape.BIMODAL:
        return (width / 2.0) * sqrt(2 * (member_count // 2) / member_count)
    return width * sqrt((member_count + 1) / (12.0 * (member_count - 1)))


def evaluate_design(
    plan: TemperamentDesignPlan,
    population: PolicyPopulation,
) -> DesignEvaluation:
    """Measure realized distribution against the explicit design target."""
    fits: list[AxisFit] = []
    errors: list[float] = []
    for target in plan.targets:
        weighted = _weighted_axis_values(population, target.axis_id)
        mean = sum(value * weight for value, weight in weighted)
        variance = sum(weight * (value - mean) ** 2 for value, weight in weighted)
        spread = sqrt(variance)
        mean_error = abs(mean - target.mean)

        target_spread = _target_spread(target, len(population.members))

        spread_error = abs(spread - target_spread)
        errors.extend((mean_error, spread_error))
        fits.append(
            AxisFit(
                axis_id=target.axis_id,
                target_mean=target.mean,
                observed_mean=mean,
                target_spread=target_spread,
                observed_spread=spread,
                mean_error=mean_error,
                spread_error=spread_error,
            )
        )

    return DesignEvaluation(
        axis_fit=tuple(fits),
        mean_absolute_error=sum(errors) / len(errors),
        diversity=population_diversity(population),
        member_count=len(population.members),
    )


def design_axes(plan: TemperamentDesignPlan) -> tuple[ConditionAxis, ...]:
    """Project a design into the bounded condition-axis vocabulary it admits."""
    return tuple(
        ConditionAxis(
            axis_id=target.axis_id,
            lower=0.0,
            upper=1.0,
            provenance_refs=target.evidence_refs,
        )
        for target in plan.targets
    )
