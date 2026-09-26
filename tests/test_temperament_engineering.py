from __future__ import annotations

import pytest

from gymact.policy_ecology import ReactionNorm
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
    evaluate_design,
    manufacture_population,
)


def plan(
    *,
    topology: ControlTopology = ControlTopology.DECENTRALIZED,
    reaction_norm: ReactionNorm | None = None,
    platform_traits: tuple[PlatformTrait, ...] = (),
) -> TemperamentDesignPlan:
    return TemperamentDesignPlan(
        mission_id="mission:explore-and-cover",
        topology=topology,
        mode=(
            DesignMode.OFFLINE_ANTICIPATORY
            if topology is ControlTopology.DECENTRALIZED
            else DesignMode.ONLINE_PLANNER_OUTPUT
        ),
        criteria=(
            MissionCriterion(
                criterion_id="coverage",
                axis_weights=(("exploration", 3.0), ("activity", 1.0)),
            ),
            MissionCriterion(
                criterion_id="resilience",
                axis_weights=(("exploration", 1.0), ("initiative", 2.0)),
            ),
        ),
        targets=(
            AxisTarget(
                axis_id="exploration",
                mean=0.5,
                spread=0.5,
                shape=DistributionShape.UNIFORM,
            ),
            AxisTarget(
                axis_id="initiative",
                mean=0.5,
                spread=0.25,
                shape=DistributionShape.BIMODAL,
            ),
        ),
        reaction_norm=reaction_norm,
        platform_traits=platform_traits,
        evidence_refs=("https://arxiv.org/abs/2609.29423",),
    )


def test_axis_relevance_aggregates_explicit_mission_mapping() -> None:
    relevance = axis_relevance(plan().criteria)
    assert [item.axis_id for item in relevance] == ["exploration", "initiative", "activity"]
    assert sum(item.score for item in relevance) == pytest.approx(1.0)
    assert relevance[0].score == pytest.approx(4.0 / 7.0)


def test_decentralized_swarm_refuses_online_reassignment_design() -> None:
    with pytest.raises(
        ValueError,
        match="REFUSED:DECENTRALIZED_SWARM_REQUIRES_ANTICIPATORY_DESIGN",
    ):
        TemperamentDesignPlan(
            mission_id="m",
            topology=ControlTopology.DECENTRALIZED,
            mode=DesignMode.ONLINE_PLANNER_OUTPUT,
            criteria=(
                MissionCriterion(
                    criterion_id="coverage",
                    axis_weights=(("exploration", 1.0),),
                ),
            ),
            targets=(AxisTarget(axis_id="exploration", mean=0.5),),
        )


def test_manufacture_population_realizes_distribution_without_authority() -> None:
    population = manufacture_population(plan(), policy_ref="planner:Astar", member_count=5)
    assert len(population.members) == 5
    assert population.kind.value == "engineered"
    assert [member.phenotype.condition.as_dict()["exploration"] for member in population.members] == [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
    ]
    assert {
        member.phenotype.policy_ref for member in population.members
    } == {"planner:Astar"}
    assert all(
        "authority" not in member.phenotype.condition.as_dict()
        for member in population.members
    )


def test_adaptive_design_preserves_reaction_norm_as_population_capability() -> None:
    reaction_norm = ReactionNorm(slopes=(("exploration", 0.5),))
    population = manufacture_population(
        plan(reaction_norm=reaction_norm),
        policy_ref="planner:MCTS",
        member_count=4,
    )
    assert population.kind.value == "adaptive"
    assert population.reaction_norm == reaction_norm


def test_platform_heterogeneity_is_declared_coupling_not_hidden_randomness() -> None:
    design = plan(
        platform_traits=(
            PlatformTrait(
                trait_id="battery_margin",
                value=-0.25,
                axis_couplings=(("exploration", 0.5),),
                evidence_refs=("urn:evidence:battery-telemetry",),
            ),
        )
    )
    base = manufacture_population(design, policy_ref="planner:Astar", member_count=3)
    conditioned = apply_platform_heterogeneity(base, design)

    before = [
        member.phenotype.condition.as_dict()["exploration"]
        for member in base.members
    ]
    after = [
        member.phenotype.condition.as_dict()["exploration"]
        for member in conditioned.members
    ]
    assert before == [0.0, 0.5, 1.0]
    assert after == [0.0, 0.375, 0.875]
    assert all(
        "urn:evidence:battery-telemetry" in member.phenotype.evidence_refs
        for member in conditioned.members
    )


def test_design_evaluation_distinguishes_distribution_fit_from_diversity() -> None:
    design = plan()
    population = manufacture_population(design, policy_ref="planner:Astar", member_count=5)
    evaluation = evaluate_design(design, population)

    assert evaluation.member_count == 5
    assert evaluation.diversity.complexity == pytest.approx(5.0)
    assert evaluation.diversity.disparity > 0.0
    assert {fit.axis_id for fit in evaluation.axis_fit} == {"exploration", "initiative"}
    exploration = next(fit for fit in evaluation.axis_fit if fit.axis_id == "exploration")
    assert exploration.observed_mean == pytest.approx(0.5)
    assert exploration.mean_error == pytest.approx(0.0)


def test_design_target_cannot_smuggle_authority_axis() -> None:
    with pytest.raises(ValueError, match="REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY"):
        TemperamentDesignPlan(
            mission_id="m",
            topology=ControlTopology.CENTRALIZED,
            mode=DesignMode.ONLINE_PLANNER_OUTPUT,
            criteria=(
                MissionCriterion(
                    criterion_id="c",
                    axis_weights=(("authority", 1.0),),
                ),
            ),
            targets=(AxisTarget(axis_id=" Authority ", mean=0.5),),
        )


def test_adaptive_reaction_norm_is_not_erased_by_homogeneous_baseline() -> None:
    design = TemperamentDesignPlan(
        mission_id="m",
        topology=ControlTopology.CENTRALIZED,
        mode=DesignMode.ONLINE_PLANNER_OUTPUT,
        criteria=(
            MissionCriterion(
                criterion_id="c",
                axis_weights=(("exploration", 1.0),),
            ),
        ),
        targets=(AxisTarget(axis_id="exploration", mean=0.5),),
        reaction_norm=ReactionNorm(slopes=(("exploration", 0.25),)),
    )
    population = manufacture_population(
        design,
        policy_ref="planner:Astar",
        member_count=3,
    )
    assert population.kind.value == "adaptive"
    assert population.reaction_norm is not None


def test_odd_bimodal_population_preserves_target_mean() -> None:
    design = TemperamentDesignPlan(
        mission_id="m:bimodal",
        topology=ControlTopology.CENTRALIZED,
        mode=DesignMode.ONLINE_PLANNER_OUTPUT,
        criteria=(
            MissionCriterion(
                criterion_id="c",
                axis_weights=(("initiative", 1.0),),
            ),
        ),
        targets=(
            AxisTarget(
                axis_id="initiative",
                mean=0.5,
                spread=0.25,
                shape=DistributionShape.BIMODAL,
            ),
        ),
    )
    population = manufacture_population(
        design,
        policy_ref="planner:Astar",
        member_count=5,
    )
    values = [
        member.phenotype.condition.as_dict()["initiative"]
        for member in population.members
    ]
    assert values == [0.25, 0.25, 0.5, 0.75, 0.75]
    assert sum(values) / len(values) == pytest.approx(0.5)
