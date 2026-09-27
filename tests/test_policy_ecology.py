from __future__ import annotations

import pytest

from gymact.policy_ecology import (
    DEFAULT_TEMPERAMENT_AXES,
    TEMPERAMENT_ENGINEERING_PROVENANCE,
    ConditionAxis,
    PolicyPhenotype,
    PolicyPopulation,
    PopulationKind,
    ReactionNorm,
    StrategicCondition,
    WeightedPhenotype,
    condition_population,
    population_diversity,
)


def phenotype(policy_ref: str, **values: float) -> PolicyPhenotype:
    return PolicyPhenotype(
        policy_ref=policy_ref,
        condition=StrategicCondition(values=tuple(sorted(values.items()))),
    )


def test_engineered_population_separates_disparity_from_complexity() -> None:
    population = PolicyPopulation(
        kind=PopulationKind.ENGINEERED,
        members=(
            WeightedPhenotype(phenotype=phenotype("policy:a", exploration=0.0), weight=1.0),
            WeightedPhenotype(phenotype=phenotype("policy:a", exploration=1.0), weight=1.0),
        ),
    )
    diversity = population_diversity(population)
    assert diversity.disparity == pytest.approx(1.0)
    assert diversity.complexity == pytest.approx(2.0)


def test_homogeneous_population_has_zero_disparity_and_unit_complexity() -> None:
    population = PolicyPopulation(
        kind=PopulationKind.HOMOGENEOUS,
        members=(
            WeightedPhenotype(
                phenotype=phenotype("policy:a", initiative=0.5),
                weight=7.0,
            ),
        ),
    )
    diversity = population_diversity(population)
    assert diversity.disparity == 0.0
    assert diversity.complexity == pytest.approx(1.0)


def test_reaction_norm_changes_behavior_but_preserves_policy_identity_and_weight() -> None:
    population = PolicyPopulation(
        kind=PopulationKind.ADAPTIVE,
        reaction_norm=ReactionNorm(
            slopes=(("exploration", 0.75), ("initiative", 1.0)),
            reference_cue=0.0,
        ),
        members=(
            WeightedPhenotype(
                phenotype=phenotype(
                    "planner:Astar",
                    exploration=0.25,
                    initiative=0.4,
                ),
                weight=3.0,
            ),
        ),
    )
    conditioned = condition_population(
        population,
        cue=1.0,
        axes=(
            ConditionAxis(axis_id="exploration", lower=0.0, upper=1.0),
            ConditionAxis(axis_id="initiative", lower=0.0, upper=0.8),
        ),
    )
    member = conditioned.members[0]
    assert member.phenotype.policy_ref == "planner:Astar"
    assert member.weight == 3.0
    assert member.phenotype.condition.as_dict() == {
        "exploration": 1.0,
        "initiative": 0.8,
    }


@pytest.mark.parametrize(
    "axis_id",
    [
        "authority",
        "permission",
        "execution_grant",
        "execution_authority",
        "do",
        " Authority ",
        "EXECUTION_GRANT",
    ],
)
def test_temperament_cannot_encode_authority(axis_id: str) -> None:
    with pytest.raises(ValueError, match="REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY"):
        StrategicCondition(values=((axis_id, 1.0),))


def test_adaptive_population_requires_reaction_norm() -> None:
    with pytest.raises(ValueError, match="REFUSED:ADAPTIVE_POPULATION_REQUIRES_REACTION_NORM"):
        PolicyPopulation(
            kind=PopulationKind.ADAPTIVE,
            members=(WeightedPhenotype(phenotype=phenotype("policy:a"), weight=1.0),),
        )


def test_default_temperament_axes_are_bound_to_source_provenance() -> None:
    assert TEMPERAMENT_ENGINEERING_PROVENANCE == ("https://arxiv.org/abs/2609.29423",)
    assert all(
        axis.provenance_refs == TEMPERAMENT_ENGINEERING_PROVENANCE
        for axis in DEFAULT_TEMPERAMENT_AXES
    )
