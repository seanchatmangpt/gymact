"""Condition policy populations without turning behavioral variation into authority.

This module adds the policy-population layer described by arXiv:2609.29423 to
GymAct's existing reversible ecology substrate. It remains candidate-only:
strategic conditioning changes search/coordination behavior, never execution
permission, authority standing, or the BRCE DO gate.
"""

from __future__ import annotations

from enum import StrEnum
from math import sqrt
from typing import Self

from pydantic import Field, model_validator

from gymact.models import FrozenModel

TEMPERAMENT_ENGINEERING_PROVENANCE = ("https://arxiv.org/abs/2609.29423",)

_FORBIDDEN_AUTHORITY_AXES = frozenset(
    {
        "authority",
        "permission",
        "execution_grant",
        "execution_authority",
        "do",
    }
)


def _normalized_axis_id(axis_id: str) -> str:
    return axis_id.strip().lower()


class PopulationKind(StrEnum):
    HOMOGENEOUS = "homogeneous"
    INCIDENTAL = "incidental"
    ENGINEERED = "engineered"
    ADAPTIVE = "adaptive"


class ConditionAxis(FrozenModel):
    axis_id: str = Field(min_length=1)
    lower: float = 0.0
    upper: float = 1.0
    provenance_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_axis(self) -> Self:
        if _normalized_axis_id(self.axis_id) in _FORBIDDEN_AUTHORITY_AXES:
            raise ValueError(f"REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY:{self.axis_id}")
        if self.lower >= self.upper:
            raise ValueError("REFUSED:CONDITION_AXIS_REQUIRES_NONEMPTY_RANGE")
        return self


class StrategicCondition(FrozenModel):
    """A point on a behavioral conditioning manifold.

    Values intentionally contain no authority field. The validator also
    refuses common authority-like axis names so callers cannot disguise a
    grant as a behavioral parameter.
    """

    values: tuple[tuple[str, float], ...] = ()

    @model_validator(mode="after")
    def unique_non_authority_axes(self) -> Self:
        keys = [key for key, _ in self.values]
        if len(keys) != len(set(keys)):
            raise ValueError("REFUSED:DUPLICATE_CONDITION_AXIS")
        forbidden = [
            key for key in keys if _normalized_axis_id(key) in _FORBIDDEN_AUTHORITY_AXES
        ]
        if forbidden:
            raise ValueError(
                f"REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY:{sorted(forbidden)[0]}"
            )
        return self

    def as_dict(self) -> dict[str, float]:
        return dict(self.values)


class ReactionNorm(FrozenModel):
    """Linear cue response around a reference cue.

    condition(c) = baseline + slope * (c - reference_cue), clamped to each
    declared axis range.
    """

    slopes: tuple[tuple[str, float], ...] = ()
    reference_cue: float = 0.0

    @model_validator(mode="after")
    def unique_non_authority_axes(self) -> Self:
        keys = [key for key, _ in self.slopes]
        if len(keys) != len(set(keys)):
            raise ValueError("REFUSED:DUPLICATE_REACTION_NORM_AXIS")
        forbidden = [
            key for key in keys if _normalized_axis_id(key) in _FORBIDDEN_AUTHORITY_AXES
        ]
        if forbidden:
            raise ValueError(
                f"REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY:{sorted(forbidden)[0]}"
            )
        return self

    def apply(
        self,
        baseline: StrategicCondition,
        cue: float,
        axes: tuple[ConditionAxis, ...],
    ) -> StrategicCondition:
        ranges = {axis.axis_id: axis for axis in axes}
        values = baseline.as_dict()
        delta = cue - self.reference_cue
        for axis_id, slope in self.slopes:
            if axis_id not in ranges:
                raise ValueError(f"REFUSED:UNKNOWN_CONDITION_AXIS:{axis_id}")
            axis = ranges[axis_id]
            value = values.get(axis_id, axis.lower) + slope * delta
            values[axis_id] = min(axis.upper, max(axis.lower, value))
        return StrategicCondition(values=tuple(sorted(values.items())))


class PolicyPhenotype(FrozenModel):
    """One conditioned realization of an existing policy."""

    policy_ref: str = Field(min_length=1)
    condition: StrategicCondition = Field(default_factory=StrategicCondition)
    evidence_refs: tuple[str, ...] = ()


class WeightedPhenotype(FrozenModel):
    phenotype: PolicyPhenotype
    weight: float = Field(gt=0.0)


class PolicyPopulation(FrozenModel):
    kind: PopulationKind
    members: tuple[WeightedPhenotype, ...] = Field(min_length=1)
    reaction_norm: ReactionNorm | None = None

    @model_validator(mode="after")
    def population_contract(self) -> Self:
        if self.kind is PopulationKind.HOMOGENEOUS and len(self.members) != 1:
            raise ValueError("REFUSED:HOMOGENEOUS_POPULATION_REQUIRES_ONE_PHENOTYPE")
        if self.kind is PopulationKind.ADAPTIVE and self.reaction_norm is None:
            raise ValueError("REFUSED:ADAPTIVE_POPULATION_REQUIRES_REACTION_NORM")
        return self

    def normalized_weights(self) -> tuple[float, ...]:
        total = sum(member.weight for member in self.members)
        return tuple(member.weight / total for member in self.members)


class PopulationDiversity(FrozenModel):
    disparity: float = Field(ge=0.0)
    complexity: float = Field(ge=1.0)


DEFAULT_TEMPERAMENT_AXES: tuple[ConditionAxis, ...] = tuple(
    ConditionAxis(
        axis_id=axis_id,
        provenance_refs=TEMPERAMENT_ENGINEERING_PROVENANCE,
    )
    for axis_id in (
        "boldness",
        "exploration",
        "activity",
        "aggressiveness",
        "sociability",
        "self_model_plasticity",
        "forcefulness",
        "initiative",
        "expressiveness",
    )
)


def condition_population(
    population: PolicyPopulation,
    *,
    cue: float,
    axes: tuple[ConditionAxis, ...] = DEFAULT_TEMPERAMENT_AXES,
) -> PolicyPopulation:
    """Apply an adaptive reaction norm without changing policy identity or weight."""
    if population.kind is not PopulationKind.ADAPTIVE:
        return population
    assert population.reaction_norm is not None
    return PolicyPopulation(
        kind=population.kind,
        reaction_norm=population.reaction_norm,
        members=tuple(
            WeightedPhenotype(
                phenotype=PolicyPhenotype(
                    policy_ref=member.phenotype.policy_ref,
                    condition=population.reaction_norm.apply(
                        member.phenotype.condition,
                        cue,
                        axes,
                    ),
                    evidence_refs=member.phenotype.evidence_refs,
                ),
                weight=member.weight,
            )
            for member in population.members
        ),
    )


def population_diversity(population: PolicyPopulation) -> PopulationDiversity:
    """Return weighted geometric disparity and effective population complexity.

    Disparity is the weighted mean pairwise Euclidean distance over the union
    of condition axes. Complexity is the inverse Simpson effective member
    count. They are intentionally separate: two populations can have the same
    member count but radically different behavioral separation.
    """
    weights = population.normalized_weights()
    conditions = [member.phenotype.condition.as_dict() for member in population.members]

    disparity = 0.0
    pair_weight = 0.0
    for left in range(len(conditions)):
        for right in range(left + 1, len(conditions)):
            keys = set(conditions[left]) | set(conditions[right])
            distance = sqrt(
                sum(
                    (conditions[left].get(key, 0.0) - conditions[right].get(key, 0.0)) ** 2
                    for key in keys
                )
            )
            weight = weights[left] * weights[right]
            disparity += weight * distance
            pair_weight += weight

    if pair_weight:
        disparity /= pair_weight

    complexity = 1.0 / sum(weight * weight for weight in weights)
    return PopulationDiversity(disparity=disparity, complexity=complexity)
