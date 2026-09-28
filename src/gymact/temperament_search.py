"""Reversible DfCM search over temperament-engineering designs.

The search portfolio preserves distribution/reaction-norm alternatives until an
external experiment supplies evidence. It never selects a winner and never
carries execution authority.
"""

from __future__ import annotations

from collections.abc import Iterable
from math import fsum

from pydantic import Field, model_validator

from gymact.combinatorial import (
    ExplorationBounds,
    Factor,
    manufacture_combination_space,
)
from gymact.evidence import digest
from gymact.models import FrozenModel
from gymact.policy_ecology import ReactionNorm
from gymact.temperament_engineering import (
    AxisTarget,
    ControlTopology,
    DesignMode,
    DistributionShape,
    MissionCriterion,
    TemperamentDesignPlan,
    axis_relevance,
)


class AxisDesignOption(FrozenModel):
    option_id: str = Field(min_length=1)
    mean: float = Field(ge=0.0, le=1.0)
    spread: float = Field(default=0.0, ge=0.0, le=0.5)
    shape: DistributionShape = DistributionShape.POINT
    cue_slope: float = 0.0
    engineering_cost: float = Field(default=0.0, ge=0.0)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_target(self) -> "AxisDesignOption":
        AxisTarget(
            axis_id="validation",
            mean=self.mean,
            spread=self.spread,
            shape=self.shape,
            cue_slope=self.cue_slope,
            evidence_refs=self.evidence_refs,
        )
        return self


class AxisDesignSpace(FrozenModel):
    axis_id: str = Field(min_length=1)
    options: tuple[AxisDesignOption, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_options(self) -> "AxisDesignSpace":
        ids = [option.option_id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError(f"REFUSED:DUPLICATE_AXIS_DESIGN_OPTION:{self.axis_id}")
        AxisTarget(axis_id=self.axis_id, mean=0.5)
        return self


class DesignObjectiveVector(FrozenModel):
    relevant_spread: float = Field(ge=0.0)
    adaptive_capacity: float = Field(ge=0.0)
    engineering_cost: float = Field(ge=0.0)
    implementation_complexity: int = Field(ge=0)

    def dominates(self, other: "DesignObjectiveVector") -> bool:
        no_worse = (
            self.relevant_spread >= other.relevant_spread
            and self.adaptive_capacity >= other.adaptive_capacity
            and self.engineering_cost <= other.engineering_cost
            and self.implementation_complexity <= other.implementation_complexity
        )
        strictly_better = (
            self.relevant_spread > other.relevant_spread
            or self.adaptive_capacity > other.adaptive_capacity
            or self.engineering_cost < other.engineering_cost
            or self.implementation_complexity < other.implementation_complexity
        )
        return no_worse and strictly_better


class TemperamentDesignCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    option_ids: tuple[tuple[str, str], ...]
    plan: TemperamentDesignPlan
    objectives: DesignObjectiveVector

    @property
    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class TemperamentDesignPortfolio(FrozenModel):
    candidates: tuple[TemperamentDesignCandidate, ...]
    total_cardinality: int = Field(ge=0)
    truncated: bool
    explored_cardinality: int = Field(ge=0)

    @model_validator(mode="after")
    def portfolio_cardinality(self) -> "TemperamentDesignPortfolio":
        if self.explored_cardinality != len(self.candidates):
            raise ValueError("REFUSED:DESIGN_PORTFOLIO_CARDINALITY_MISMATCH")
        if self.explored_cardinality > self.total_cardinality:
            raise ValueError("REFUSED:DESIGN_PORTFOLIO_EXCEEDS_FULL_SPACE")
        return self


def _criterion_relevance(
    criteria: tuple[MissionCriterion, ...],
) -> dict[str, float]:
    return {item.axis_id: item.score for item in axis_relevance(criteria)}


def _validate_search_axes(
    criteria: tuple[MissionCriterion, ...],
    spaces: tuple[AxisDesignSpace, ...],
) -> None:
    ids = [space.axis_id for space in spaces]
    if len(ids) != len(set(ids)):
        raise ValueError("REFUSED:DUPLICATE_AXIS_DESIGN_SPACE")

    relevant = {
        axis
        for criterion in criteria
        for axis, weight in criterion.axis_weights
        if weight > 0.0
    }
    missing = relevant.difference(ids)
    if missing:
        raise ValueError(
            "REFUSED:MISSION_AXIS_MISSING_FROM_DESIGN_SPACE:"
            + ",".join(sorted(missing))
        )


def manufacture_design_portfolio(
    *,
    mission_id: str,
    topology: ControlTopology,
    mode: DesignMode,
    criteria: tuple[MissionCriterion, ...],
    spaces: tuple[AxisDesignSpace, ...],
    platform_traits: tuple = (),
    evidence_refs: tuple[str, ...] = (),
    max_candidates: int = 4096,
) -> TemperamentDesignPortfolio:
    """Manufacture a bounded Cartesian design portfolio without choosing."""
    if max_candidates < 1:
        raise ValueError("REFUSED:MAX_DESIGN_CANDIDATES_MUST_BE_POSITIVE")
    _validate_search_axes(criteria, spaces)

    option_index = {
        (space.axis_id, option.option_id): option
        for space in spaces
        for option in space.options
    }
    combination_space = manufacture_combination_space(
        tuple(
            Factor(
                factor_id=space.axis_id,
                alternatives=tuple(option.option_id for option in space.options),
            )
            for space in spaces
        ),
        bounds=ExplorationBounds(max_combinations=max_candidates),
    )
    relevance = _criterion_relevance(criteria)

    candidates: list[TemperamentDesignCandidate] = []
    for combination in combination_space.combinations:
        selected = tuple(
            (
                axis_id,
                option_index[(axis_id, option_id)],
            )
            for axis_id, option_id in sorted(combination.assignments.items())
        )
        targets = tuple(
            AxisTarget(
                axis_id=axis_id,
                mean=option.mean,
                spread=option.spread,
                shape=option.shape,
                cue_slope=option.cue_slope,
                evidence_refs=option.evidence_refs,
            )
            for axis_id, option in selected
        )
        slopes = tuple(
            (axis_id, option.cue_slope)
            for axis_id, option in selected
            if option.cue_slope != 0.0
        )
        reaction_norm = ReactionNorm(slopes=slopes) if slopes else None
        plan = TemperamentDesignPlan(
            mission_id=mission_id,
            topology=topology,
            mode=mode,
            criteria=criteria,
            targets=targets,
            reaction_norm=reaction_norm,
            platform_traits=platform_traits,
            evidence_refs=evidence_refs,
        )
        objectives = DesignObjectiveVector(
            relevant_spread=fsum(
                relevance.get(axis_id, 0.0) * option.spread
                for axis_id, option in selected
            ),
            adaptive_capacity=fsum(
                relevance.get(axis_id, 0.0) * abs(option.cue_slope)
                for axis_id, option in selected
            ),
            engineering_cost=fsum(option.engineering_cost for _, option in selected),
            implementation_complexity=sum(
                int(option.spread > 0.0)
                + int(option.cue_slope != 0.0)
                + int(option.shape is not DistributionShape.POINT)
                for _, option in selected
            ),
        )
        option_ids = tuple(
            (axis_id, option.option_id)
            for axis_id, option in selected
        )
        candidate_id = "urn:gymact:temperament-design:" + digest(
            {
                "plan": plan.model_dump(mode="json"),
                "options": option_ids,
            }
        )
        candidates.append(
            TemperamentDesignCandidate(
                candidate_id=candidate_id,
                option_ids=option_ids,
                plan=plan,
                objectives=objectives,
            )
        )

    return TemperamentDesignPortfolio(
        candidates=tuple(candidates),
        total_cardinality=combination_space.total_cardinality,
        truncated=combination_space.truncated,
        explored_cardinality=len(candidates),
    )


def pareto_designs(
    candidates: Iterable[TemperamentDesignCandidate],
) -> tuple[TemperamentDesignCandidate, ...]:
    """Return non-dominated candidates; no scalarization and no winner."""
    values = tuple(candidates)
    return tuple(
        candidate
        for candidate in values
        if not any(
            other.candidate_id != candidate.candidate_id
            and other.objectives.dominates(candidate.objectives)
            for other in values
        )
    )
