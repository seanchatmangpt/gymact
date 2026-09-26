"""Falsifiers for the court findings on PR #145 head badc725 (real models, real rdflib).

Each case below was a real acceptance or a real false refusal on badc725:

* a Turtle round trip refused legitimate graphs (rdflib writes xsd:double with
  ~7 significant digits, so manufactured values such as 0.36666666666666664
  came back changed and the whole-graph binding answered PROJECTION_MISMATCH);
* the authority fence admitted plural, camelCase, concatenated, zero-width-split
  and homoglyph spellings ("permissions", "ExecutionGrant", "auth\\u200bority",
  a Cyrillic small a, U+0430), so an ADAPTIVE population with those axes validated;
* the RDF triples did not pair an extent with its axis;
* ReactionNorm.apply keyed ranges by raw axis id, so a case variant skipped the
  range check;
* temperament criteria admitted an axis id that normalizes to empty;
* odd-n BIMODAL manufacture and the continuous-uniform spread formula made a
  perfect manufacture report nonzero error, and design targets were not tied
  to mission relevance.
"""

from __future__ import annotations

import pytest
from rdflib import Graph, Literal
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

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
)
from gymact.policy_ecology_rdf import (
    policy_population_to_rdf,
    rdf_to_policy_population,
    validate_policy_ecology_rdf,
)
from gymact.temperament_engineering import (
    AxisTarget,
    ControlTopology,
    DesignMode,
    DistributionShape,
    MissionCriterion,
    PlatformTrait,
    TemperamentDesignPlan,
    evaluate_design,
    manufacture_population,
)

FENCE = "REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY"

# Every spelling the two courts admitted on badc725, plus derived forms.
BYPASS_SPELLINGS = (
    "permissions",
    "Permissions",
    "authorities",
    "ExecutionGrant",
    "executionGrant",
    "authorityLevel",
    "executiongrant",
    "authorization",
    "authoritative",
    "auth",
    "grant",
    "execute",
    "privilege",
    "capability",
    "d o",
    "do_action",
    "can_do",
    "canDo",
    "auth\u200bority",
    "authorit\u0443",  # Cyrillic u
    "\u0430uthority",  # Cyrillic a
    "permissionSet",
    "sudo",
)

BENIGN_SPELLINGS = (
    "granularity",
    "dominance",
    "outdoor",
    "authenticity",
    "selfModel",
    "self_model_plasticity",
    "exploration",
)


def weighted(ref: str, weight: float = 1.0, **values: float) -> WeightedPhenotype:
    return WeightedPhenotype(
        phenotype=PolicyPhenotype(
            policy_ref=ref,
            condition=StrategicCondition(values=tuple(values.items())),
        ),
        weight=weight,
    )


def design(
    *targets: AxisTarget, criteria_axes: tuple[str, ...] | None = None
) -> TemperamentDesignPlan:
    axes = criteria_axes or tuple(target.axis_id for target in targets)
    return TemperamentDesignPlan(
        mission_id="mission:court",
        topology=ControlTopology.CENTRALIZED,
        mode=DesignMode.ONLINE_PLANNER_OUTPUT,
        criteria=(
            MissionCriterion(criterion_id="c", axis_weights=tuple((axis, 1.0) for axis in axes)),
        ),
        targets=targets,
    )


# --- MAJOR: Turtle round trip -------------------------------------------------


def _manufactured() -> PolicyPopulation:
    plan = design(
        AxisTarget(axis_id="boldness", mean=0.5, spread=0.2, shape=DistributionShape.UNIFORM)
    )
    population = manufacture_population(plan, policy_ref="planner:Astar", member_count=7)
    values = [m.phenotype.condition.as_dict()["boldness"] for m in population.members]
    # the repro: non-terminating manufactured values, more than 7 digits
    assert any(len(repr(value)) > 12 for value in values)
    return population


def _edge_values() -> PolicyPopulation:
    return PolicyPopulation(
        kind=PopulationKind.ENGINEERED,
        members=(
            weighted("planner:A", boldness=0.123456789, exploration=1e-7),
            weighted("planner:B", boldness=1e300, exploration=-2.5e-12),
            weighted("planner:C", boldness=0.1 + 0.2, exploration=0.0),
        ),
    )


@pytest.mark.parametrize("fmt", ["turtle", "nt", "xml", "json-ld", "n3"])
@pytest.mark.parametrize("build", [_manufactured, _edge_values])
def test_lossless_projection_survives_every_serialization(fmt: str, build) -> None:
    population = build()
    graph = policy_population_to_rdf(population)
    parsed = Graph().parse(data=graph.serialize(format=fmt), format=fmt)
    report = validate_policy_ecology_rdf(parsed)
    assert report.conforms, report.report_text
    assert rdf_to_policy_population(parsed) == population
    # and a second serialization hop is still admitted
    again = Graph().parse(data=parsed.serialize(format=fmt), format=fmt)
    assert rdf_to_policy_population(again) == population


def test_turtle_round_trip_still_refuses_a_changed_value() -> None:
    population = _manufactured()
    text = policy_population_to_rdf(population).serialize(format="turtle")
    original = population.members[1].phenotype.condition.as_dict()["boldness"]
    # full precision is carried in the Turtle text, not a 7-digit rewrite
    assert repr(original) in text
    parsed = Graph().parse(data=text, format="turtle")
    (cell, value) = next(
        (cell, value)
        for cell, value in parsed.subject_objects(RDF.value)
        if isinstance(value, Literal)
        and value.datatype == XSD.decimal
        and float(str(value)) == original
    )
    parsed.remove((cell, RDF.value, value))
    parsed.add((cell, RDF.value, Literal("0.3666667", datatype=XSD.decimal)))
    report = validate_policy_ecology_rdf(parsed)
    assert not report.conforms
    assert "REFUSED:POLICY_ECOLOGY_RDF_PROJECTION_MISMATCH" in report.report_text


# --- MINOR: axis/value pairing readable from triples -------------------------


def test_axis_value_pairing_is_recoverable_from_triples_alone() -> None:
    population = PolicyPopulation(
        kind=PopulationKind.ENGINEERED,
        members=(
            weighted("planner:A", boldness=0.5, exploration=0.5, activity=0.25),
            weighted("planner:B", boldness=0.75, exploration=0.5, activity=0.75),
        ),
    )
    graph = policy_population_to_rdf(population)
    root = next(iter(graph.subjects(DCTERMS.conformsTo, None)))
    for member in graph.objects(root, DCTERMS.hasPart):
        (index,) = tuple(graph.objects(member, DCTERMS.identifier))
        recovered: dict[str, float] = {}
        for cell in graph.subjects(DCTERMS.isPartOf, member):
            (concept,) = tuple(graph.objects(cell, DCTERMS.subject))
            (notation,) = tuple(graph.objects(concept, SKOS.notation))
            (value,) = tuple(graph.objects(cell, RDF.value))
            recovered[str(notation)] = float(str(value))
        expected = population.members[int(str(index))].phenotype.condition.as_dict()
        # equal values on distinct axes stay distinct (0.5 twice for member A)
        assert recovered == expected


# --- MAJOR: authority fence ---------------------------------------------------


@pytest.mark.parametrize("axis_id", BYPASS_SPELLINGS)
def test_authority_spellings_are_refused_on_every_surface(axis_id: str) -> None:
    with pytest.raises(ValueError, match=FENCE):
        ConditionAxis(axis_id=axis_id)
    with pytest.raises(ValueError, match=FENCE):
        StrategicCondition(values=((axis_id, 0.5),))
    with pytest.raises(ValueError, match=FENCE):
        ReactionNorm(slopes=((axis_id, 1.0),))
    with pytest.raises(ValueError, match=FENCE):
        MissionCriterion(criterion_id="c", axis_weights=((axis_id, 1.0),))
    with pytest.raises(ValueError, match=FENCE):
        PlatformTrait(trait_id="t", value=1.0, axis_couplings=((axis_id, 1.0),))
    with pytest.raises(ValueError, match=FENCE):
        design(AxisTarget(axis_id=axis_id, mean=0.5), criteria_axes=("exploration",))


def test_court_end_to_end_adaptive_authority_population_is_refused() -> None:
    with pytest.raises(ValueError, match=FENCE):
        PolicyPopulation(
            kind=PopulationKind.ADAPTIVE,
            members=(weighted("planner:A", permissions=0.5, executionGrant=0.5),),
            reaction_norm=ReactionNorm(slopes=(("authorityLevel", 1.0),)),
        )


@pytest.mark.parametrize("axis_id", BENIGN_SPELLINGS)
def test_benign_axes_are_still_admitted(axis_id: str) -> None:
    assert ConditionAxis(axis_id=axis_id).axis_id == axis_id
    for axis in DEFAULT_TEMPERAMENT_AXES:
        ConditionAxis(axis_id=axis.axis_id)


def test_camel_case_and_separator_spellings_are_one_axis() -> None:
    with pytest.raises(ValueError, match="REFUSED:DUPLICATE_CONDITION_AXIS"):
        StrategicCondition(values=(("selfModel", 0.1), ("self_model", 0.2)))


# --- MINOR: ReactionNorm.apply normalized keys -------------------------------


def test_reaction_norm_ranges_are_keyed_by_normalized_axis() -> None:
    norm = ReactionNorm(slopes=(("boldness", 1.0),))
    with pytest.raises(ValueError, match="REFUSED:DUPLICATE_CONDITION_AXIS"):
        norm.apply(
            StrategicCondition(values=(("boldness", 0.2),)),
            0.5,
            (ConditionAxis(axis_id="boldness"), ConditionAxis(axis_id="Boldness ")),
        )
    with pytest.raises(ValueError, match="REFUSED:CONDITION_OUTSIDE_AXIS_RANGE:Boldness"):
        norm.apply(
            StrategicCondition(values=(("Boldness", 1.5),)),
            0.5,
            (ConditionAxis(axis_id="boldness"),),
        )
    conditioned = norm.apply(
        StrategicCondition(values=(("Boldness", 0.2),)),
        0.5,
        (ConditionAxis(axis_id="boldness"),),
    )
    # the variant spelling is updated in place, not duplicated
    assert conditioned.as_dict() == {"Boldness": pytest.approx(0.7)}


def test_adaptive_population_conditions_case_variant_member_axis() -> None:
    population = PolicyPopulation(
        kind=PopulationKind.ADAPTIVE,
        members=(weighted("planner:A", Boldness=0.9),),
        reaction_norm=ReactionNorm(slopes=(("boldness", 10.0),)),
    )
    conditioned = condition_population(population, cue=1.0)
    assert conditioned.members[0].phenotype.condition.as_dict() == {"Boldness": 1.0}


# --- MINOR: empty normalized axis in temperament surfaces --------------------


@pytest.mark.parametrize("axis_id", ["---", " ", "\u200b", "_._"])
def test_empty_normalized_axis_is_refused_in_temperament_surfaces(axis_id: str) -> None:
    with pytest.raises(ValueError, match="REFUSED:EMPTY_CONDITION_AXIS"):
        MissionCriterion(criterion_id="c", axis_weights=((axis_id, 1.0), ("exploration", 1.0)))
    with pytest.raises(ValueError, match="REFUSED:EMPTY_CONDITION_AXIS"):
        PlatformTrait(trait_id="t", value=1.0, axis_couplings=((axis_id, 1.0),))


# --- MINOR: distribution statistics and phase binding ------------------------


@pytest.mark.parametrize("member_count", [2, 3, 4, 5, 7, 9, 16])
@pytest.mark.parametrize("shape", [DistributionShape.UNIFORM, DistributionShape.BIMODAL])
def test_perfect_manufacture_has_zero_design_error(
    member_count: int, shape: DistributionShape
) -> None:
    plan = design(AxisTarget(axis_id="exploration", mean=0.4, spread=0.3, shape=shape))
    population = manufacture_population(plan, policy_ref="planner:A", member_count=member_count)
    (fit,) = evaluate_design(plan, population).axis_fit
    assert fit.mean_error == pytest.approx(0.0, abs=1e-12)
    assert fit.spread_error == pytest.approx(0.0, abs=1e-12)


def test_odd_bimodal_is_symmetric_about_the_target_mean() -> None:
    plan = design(
        AxisTarget(axis_id="exploration", mean=0.5, spread=0.25, shape=DistributionShape.BIMODAL)
    )
    population = manufacture_population(plan, policy_ref="planner:A", member_count=5)
    values = [m.phenotype.condition.as_dict()["exploration"] for m in population.members]
    assert values == [0.25, 0.25, 0.5, 0.75, 0.75]


@pytest.mark.parametrize(("mean", "spread"), [(0.9, 0.2), (0.1, 0.2)])
def test_target_interval_outside_unit_range_is_refused(mean: float, spread: float) -> None:
    with pytest.raises(ValueError, match="REFUSED:TARGET_INTERVAL_OUTSIDE_UNIT_RANGE:exploration"):
        AxisTarget(axis_id="exploration", mean=mean, spread=spread, shape=DistributionShape.UNIFORM)


def test_design_target_requires_mission_relevance() -> None:
    with pytest.raises(ValueError, match="REFUSED:TARGET_AXIS_WITHOUT_MISSION_RELEVANCE:boldness"):
        design(AxisTarget(axis_id="boldness", mean=0.5), criteria_axes=("exploration",))
    with pytest.raises(ValueError, match="REFUSED:TARGET_AXIS_WITHOUT_MISSION_RELEVANCE:boldness"):
        TemperamentDesignPlan(
            mission_id="m",
            topology=ControlTopology.CENTRALIZED,
            mode=DesignMode.ONLINE_PLANNER_OUTPUT,
            criteria=(
                MissionCriterion(
                    criterion_id="c", axis_weights=(("boldness", 0.0), ("exploration", 1.0))
                ),
            ),
            targets=(AxisTarget(axis_id="boldness", mean=0.5),),
        )
    # a case/separator variant of a relevant axis is the same axis
    design(AxisTarget(axis_id="Exploration", mean=0.5), criteria_axes=("exploration",))
