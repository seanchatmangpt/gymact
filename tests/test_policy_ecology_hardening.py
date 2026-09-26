"""Adversarial falsifiers for the policy-ecology authority fence and numeric contract.

Every case here was a real acceptance on PR #145 head d33e4dc before hardening
(separator/compatibility-form bypasses of the authority fence, NaN/inf
conditions, duplicate axes, unclamped out-of-range baselines, order-dependent
condition identity). Real pydantic models, no doubles.
"""

from __future__ import annotations

import math

import pytest

from gymact.policy_ecology import (
    DEFAULT_TEMPERAMENT_AXES,
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

AUTHORITY_SPELLINGS = [
    "execution-grant",
    "execution grant",
    "execution.authority",
    "Execution__Grant",
    "authority.level",
    "authority_level",
    "delegated-authority",
    "Permission-Set",
    chr(0xFF41) + "uthority",  # full-width a folds to "authority" under NFKC
    chr(0xFF24) + chr(0xFF2F),  # full-width DO
    "-do-",
    "\tDO\n",
]


def member(ref: str, weight: float = 1.0, **values: float) -> WeightedPhenotype:
    return WeightedPhenotype(
        phenotype=PolicyPhenotype(
            policy_ref=ref,
            condition=StrategicCondition(values=tuple(values.items())),
        ),
        weight=weight,
    )


def adaptive(*members: WeightedPhenotype, **slopes: float) -> PolicyPopulation:
    return PolicyPopulation(
        kind=PopulationKind.ADAPTIVE,
        reaction_norm=ReactionNorm(slopes=tuple(slopes.items())),
        members=members,
    )


@pytest.mark.parametrize("axis_id", AUTHORITY_SPELLINGS)
def test_authority_fence_survives_separator_and_compatibility_spellings(axis_id: str) -> None:
    fence = "REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY"
    with pytest.raises(ValueError, match=fence):
        StrategicCondition(values=((axis_id, 1.0),))
    with pytest.raises(ValueError, match=fence):
        ReactionNorm(slopes=((axis_id, 1.0),))
    with pytest.raises(ValueError, match=fence):
        ConditionAxis(axis_id=axis_id)


@pytest.mark.parametrize("axis_id", ["dopamine_seeking", "domain_focus", "undo_rate", "authorship"])
def test_authority_fence_does_not_refuse_benign_words_containing_fragments(axis_id: str) -> None:
    condition = StrategicCondition(values=((axis_id, 0.5),))
    assert condition.as_dict() == {axis_id: 0.5}


@pytest.mark.parametrize("axis_id", ["", "   ", "---", "..."])
def test_empty_axis_ids_are_refused(axis_id: str) -> None:
    with pytest.raises(ValueError, match=r"REFUSED:EMPTY_CONDITION_AXIS|at least 1 character"):
        ConditionAxis(axis_id=axis_id)
    with pytest.raises(ValueError, match="REFUSED:EMPTY_CONDITION_AXIS"):
        StrategicCondition(values=((axis_id, 0.5),))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_are_refused_everywhere(bad: float) -> None:
    with pytest.raises(ValueError, match="REFUSED:NON_FINITE_CONDITION_VALUE"):
        StrategicCondition(values=(("boldness", bad),))
    with pytest.raises(ValueError, match="REFUSED:NON_FINITE_CONDITION_VALUE"):
        ReactionNorm(slopes=(("boldness", bad),))
    with pytest.raises(ValueError, match="REFUSED:NON_FINITE_REFERENCE_CUE"):
        ReactionNorm(slopes=(("boldness", 1.0),), reference_cue=bad)
    with pytest.raises(ValueError, match="REFUSED:NON_FINITE_CONDITION_AXIS_BOUND"):
        ConditionAxis(axis_id="boldness", lower=bad)
    with pytest.raises(ValueError, match="REFUSED:NON_FINITE_CONDITION_AXIS_BOUND"):
        ConditionAxis(axis_id="boldness", upper=bad)
    with pytest.raises(ValueError):
        member("policy:a", weight=bad)
    with pytest.raises(ValueError, match="REFUSED:NON_FINITE_CUE"):
        condition_population(adaptive(member("policy:a"), boldness=1.0), cue=bad)


def test_overflowing_weight_total_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="REFUSED:POPULATION_WEIGHT_NOT_NORMALIZABLE"):
        PolicyPopulation(
            kind=PopulationKind.ENGINEERED,
            members=(member("policy:a", weight=1e308), member("policy:b", weight=1e308)),
        )


def test_subnormal_weight_still_normalizes_to_unit_complexity() -> None:
    population = PolicyPopulation(
        kind=PopulationKind.INCIDENTAL,
        members=(member("policy:a", weight=5e-324),),
    )
    assert population.normalized_weights() == (1.0,)
    assert population_diversity(population).complexity == 1.0


@pytest.mark.parametrize(
    ("left", "right"),
    [("boldness", "Boldness"), ("self_model_plasticity", "self-model plasticity")],
)
def test_duplicate_axes_after_normalization_are_refused(left: str, right: str) -> None:
    with pytest.raises(ValueError, match="REFUSED:DUPLICATE_CONDITION_AXIS"):
        StrategicCondition(values=((left, 0.1), (right, 0.2)))
    with pytest.raises(ValueError, match="REFUSED:DUPLICATE_REACTION_NORM_AXIS"):
        ReactionNorm(slopes=((left, 0.1), (right, 0.2)))


def test_duplicate_declared_axes_are_refused_instead_of_last_wins() -> None:
    with pytest.raises(ValueError, match="REFUSED:DUPLICATE_CONDITION_AXIS:boldness"):
        condition_population(
            adaptive(member("policy:a"), boldness=1.0),
            cue=1.0,
            axes=(
                ConditionAxis(axis_id="boldness", upper=0.5),
                ConditionAxis(axis_id="boldness", upper=1.0),
            ),
        )


def test_out_of_range_baseline_on_declared_axis_is_refused() -> None:
    population = adaptive(member("policy:a", exploration=99.0), boldness=1.0)
    with pytest.raises(ValueError, match="REFUSED:CONDITION_OUTSIDE_AXIS_RANGE:exploration"):
        condition_population(population, cue=1.0)


def test_unknown_slope_axis_is_refused() -> None:
    with pytest.raises(ValueError, match="REFUSED:UNKNOWN_CONDITION_AXIS:courage"):
        condition_population(adaptive(member("policy:a"), courage=1.0), cue=1.0)


def test_condition_identity_is_order_independent() -> None:
    left = StrategicCondition(values=(("activity", 0.2), ("boldness", 0.9)))
    right = StrategicCondition(values=(("boldness", 0.9), ("activity", 0.2)))
    assert left == right
    assert left.model_dump_json() == right.model_dump_json()
    assert ReactionNorm(slopes=(("a", 1.0), ("b", 2.0))) == ReactionNorm(
        slopes=(("b", 2.0), ("a", 1.0))
    )


def test_conditioning_is_deterministic_and_idempotent_at_the_clamp() -> None:
    population = adaptive(
        member("policy:a", weight=2.0, boldness=0.9),
        member("policy:b", weight=1.0, boldness=0.1),
        boldness=10.0,
    )
    once = condition_population(population, cue=1.0)
    replay = condition_population(population, cue=1.0)
    twice = condition_population(once, cue=1.0)
    assert once.model_dump_json() == replay.model_dump_json()
    assert once == twice  # both members pinned at the upper bound
    assert [m.phenotype.condition.as_dict()["boldness"] for m in once.members] == [1.0, 1.0]
    assert [m.weight for m in once.members] == [2.0, 1.0]
    assert [m.phenotype.policy_ref for m in once.members] == ["policy:a", "policy:b"]


def test_non_adaptive_population_is_returned_unchanged() -> None:
    population = PolicyPopulation(
        kind=PopulationKind.ENGINEERED,
        members=(member("policy:a", boldness=0.2), member("policy:b", boldness=0.8)),
    )
    assert condition_population(population, cue=1e9) is population


def test_diversity_is_invariant_under_member_reordering_and_weight_scaling() -> None:
    members = (
        member("policy:a", weight=1.0, boldness=0.0, exploration=0.0),
        member("policy:b", weight=2.0, boldness=1.0, exploration=0.0),
        member("policy:c", weight=3.0, boldness=0.0, exploration=1.0),
    )
    base = population_diversity(PolicyPopulation(kind=PopulationKind.ENGINEERED, members=members))
    reordered = population_diversity(
        PolicyPopulation(kind=PopulationKind.ENGINEERED, members=members[::-1])
    )
    scaled = population_diversity(
        PolicyPopulation(
            kind=PopulationKind.ENGINEERED,
            members=tuple(
                WeightedPhenotype(phenotype=m.phenotype, weight=m.weight * 1000.0) for m in members
            ),
        )
    )
    assert reordered.disparity == pytest.approx(base.disparity)
    assert scaled.disparity == pytest.approx(base.disparity)
    assert reordered.complexity == pytest.approx(base.complexity)
    assert scaled.complexity == pytest.approx(base.complexity)
    # inverse Simpson for weights 1:2:3 is 36/14
    assert base.complexity == pytest.approx(36.0 / 14.0)


def test_policy_phenotype_cannot_carry_an_authority_field() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        PolicyPhenotype.model_validate({"policy_ref": "policy:a", "authority": "DO"})
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        PolicyPopulation.model_validate(
            {
                "kind": "engineered",
                "members": [{"phenotype": {"policy_ref": "policy:a"}, "weight": 1.0}],
                "execution_grant": True,
            }
        )


def test_default_axes_admit_every_axis_through_the_hardened_fence() -> None:
    ids = [axis.axis_id for axis in DEFAULT_TEMPERAMENT_AXES]
    assert len(ids) == len(set(ids)) == 9
    StrategicCondition(values=tuple((axis_id, 0.5) for axis_id in ids))
