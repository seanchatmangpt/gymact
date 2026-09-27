"""Adversarial falsifiers for the three-phase temperament-engineering workflow.

Each case was a real acceptance or an untyped crash on PR #145 head cf6c023:
point designs with more than one member crashed with the homogeneous-population
refusal; a NaN platform trait silently zeroed the coupled axis; authority-named
criterion and coupling axes were admitted; case-variant duplicate targets passed
the plan and only failed later during manufacture. Real models, no doubles.
"""

from __future__ import annotations

import math

import pytest

from gymact.policy_ecology import ReactionNorm, condition_population, population_diversity
from gymact.temperament_engineering import (
    AxisTarget,
    ControlTopology,
    DesignMode,
    DistributionShape,
    MissionCriterion,
    PlatformTrait,
    TemperamentDesignPlan,
    apply_platform_heterogeneity,
    axis_relevance,
    design_axes,
    evaluate_design,
    manufacture_population,
)

CRITERIA = (MissionCriterion(criterion_id="coverage", axis_weights=(("exploration", 1.0),)),)


def plan(
    *targets: AxisTarget,
    reaction_norm: ReactionNorm | None = None,
    platform_traits: tuple[PlatformTrait, ...] = (),
) -> TemperamentDesignPlan:
    return TemperamentDesignPlan(
        mission_id="mission:m",
        topology=ControlTopology.CENTRALIZED,
        mode=DesignMode.ONLINE_PLANNER_OUTPUT,
        criteria=CRITERIA,
        targets=targets or (AxisTarget(axis_id="exploration", mean=0.5),),
        reaction_norm=reaction_norm,
        platform_traits=platform_traits,
    )


@pytest.mark.parametrize("member_count", [1, 2, 7])
def test_point_design_collapses_to_one_phenotype_carrying_all_mass(member_count: int) -> None:
    population = manufacture_population(plan(), policy_ref="planner:A", member_count=member_count)
    assert population.kind.value == "homogeneous"
    assert len(population.members) == 1
    assert population.members[0].weight == float(member_count)
    diversity = population_diversity(population)
    assert diversity.disparity == 0.0
    assert diversity.complexity == 1.0


def test_platform_coupling_outside_design_is_refused_even_when_zero() -> None:
    with pytest.raises(ValueError, match="REFUSED:PLATFORM_COUPLING_OUTSIDE_DESIGN:activity"):
        plan(
            platform_traits=(
                PlatformTrait(trait_id="battery", value=1.0, axis_couplings=(("activity", 0.0),)),
            )
        )


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_platform_traits_are_refused(bad: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        PlatformTrait(trait_id="battery", value=bad, axis_couplings=(("exploration", 1.0),))
    with pytest.raises(ValueError, match="REFUSED:NON_FINITE_PLATFORM_AXIS_COUPLING:exploration"):
        PlatformTrait(trait_id="battery", value=1.0, axis_couplings=(("exploration", bad),))


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_non_finite_mission_relevance_is_a_typed_refusal(bad: float) -> None:
    with pytest.raises(ValueError, match="REFUSED:NON_FINITE_AXIS_RELEVANCE:exploration"):
        MissionCriterion(criterion_id="c", axis_weights=(("exploration", bad), ("activity", 1.0)))


def test_non_finite_cue_slope_is_refused() -> None:
    with pytest.raises(ValueError, match="finite"):
        AxisTarget(axis_id="exploration", mean=0.5, cue_slope=math.nan)


@pytest.mark.parametrize("axis_id", ["authority", "execution-grant", "Permission.Level", "DO"])
def test_authority_axes_are_refused_in_every_design_surface(axis_id: str) -> None:
    fence = "REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY"
    with pytest.raises(ValueError, match=fence):
        MissionCriterion(criterion_id="c", axis_weights=((axis_id, 1.0),))
    with pytest.raises(ValueError, match=fence):
        PlatformTrait(trait_id="t", value=1.0, axis_couplings=((axis_id, 1.0),))
    with pytest.raises(ValueError, match=fence):
        plan(AxisTarget(axis_id=axis_id, mean=0.5))


def test_case_variant_duplicate_targets_are_refused_at_plan_admission() -> None:
    with pytest.raises(ValueError, match="REFUSED:DUPLICATE_TEMPERAMENT_TARGET"):
        plan(
            AxisTarget(axis_id="exploration", mean=0.5),
            AxisTarget(axis_id="Exploration", mean=0.2),
        )
    with pytest.raises(ValueError, match="REFUSED:DUPLICATE_CRITERION_AXIS"):
        MissionCriterion(criterion_id="c", axis_weights=(("activity", 1.0), ("ACTIVITY", 1.0)))


def test_reaction_norm_outside_design_is_refused() -> None:
    with pytest.raises(ValueError, match="REFUSED:REACTION_NORM_OUTSIDE_DESIGN:boldness"):
        plan(reaction_norm=ReactionNorm(slopes=(("boldness", 1.0),)))


def test_adaptive_design_conditions_within_its_projected_axes() -> None:
    design = plan(
        AxisTarget(axis_id="exploration", mean=0.5, spread=0.5, shape=DistributionShape.UNIFORM),
        reaction_norm=ReactionNorm(slopes=(("exploration", 1.0),)),
    )
    population = manufacture_population(design, policy_ref="planner:A", member_count=3)
    conditioned = condition_population(population, cue=0.25, axes=design_axes(design))
    values = [m.phenotype.condition.as_dict()["exploration"] for m in conditioned.members]
    assert values == [0.25, 0.75, 1.0]
    evaluation = evaluate_design(design, population)
    assert evaluation.axis_fit[0].mean_error == pytest.approx(0.0)


def test_axis_relevance_is_deterministic_and_normalized() -> None:
    criteria = (
        MissionCriterion(criterion_id="a", axis_weights=(("b", 1.0), ("a", 1.0))),
        MissionCriterion(criterion_id="b", axis_weights=(("c", 2.0),)),
    )
    first = axis_relevance(criteria)
    assert [r.axis_id for r in first] == ["c", "a", "b"]
    assert sum(r.score for r in first) == pytest.approx(1.0)
    assert first == axis_relevance(criteria)


def test_platform_heterogeneity_is_clamped_and_deterministic() -> None:
    trait = PlatformTrait(trait_id="payload", value=10.0, axis_couplings=(("exploration", 1.0),))
    design = plan(
        AxisTarget(axis_id="exploration", mean=0.5, spread=0.5, shape=DistributionShape.UNIFORM),
        platform_traits=(trait,),
    )
    base = manufacture_population(design, policy_ref="planner:A", member_count=3)
    once = apply_platform_heterogeneity(base, design)
    assert [m.phenotype.condition.as_dict()["exploration"] for m in once.members] == [1.0] * 3
    assert once.model_dump_json() == apply_platform_heterogeneity(base, design).model_dump_json()
