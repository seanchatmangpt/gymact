"""Adversarial falsifiers for the policy-ecology RDF projection.

On PR #145 head 39f13ac the admission checked only the root's canonical value
and digest, so a tampered member-level value, a dropped member, or an injected
foreign member still validated as conforming; and non-IRI policy/evidence refs
produced graphs that failed at Turtle serialization time. Real rdflib/pyshacl.
"""

from __future__ import annotations

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

from gymact.policy_ecology import (
    PolicyPhenotype,
    PolicyPopulation,
    PopulationKind,
    StrategicCondition,
    WeightedPhenotype,
)
from gymact.policy_ecology_rdf import (
    policy_population_to_rdf,
    population_digest,
    rdf_to_policy_population,
    validate_policy_ecology_rdf,
)

PROV_ENTITY = URIRef("http://www.w3.org/ns/prov#Entity")


def member(ref: str, weight: float, **values: float) -> WeightedPhenotype:
    return WeightedPhenotype(
        phenotype=PolicyPhenotype(
            policy_ref=ref,
            condition=StrategicCondition(values=tuple(values.items())),
            evidence_refs=("https://arxiv.org/abs/2609.29423",),
        ),
        weight=weight,
    )


def population() -> PolicyPopulation:
    return PolicyPopulation(
        kind=PopulationKind.ENGINEERED,
        members=(
            member("planner:A", 1.0, boldness=0.1, exploration=0.4),
            member("planner:B", 2.0, boldness=0.9, exploration=0.6),
        ),
    )


def _root(graph: Graph) -> URIRef:
    (root,) = tuple(graph.subjects(DCTERMS.conformsTo, None))
    assert isinstance(root, URIRef)
    return root


def _refused(graph: Graph) -> str:
    report = validate_policy_ecology_rdf(graph)
    assert not report.conforms
    assert report.population_digest is None
    return report.report_text


def test_clean_projection_conforms_and_round_trips_through_turtle() -> None:
    source = population()
    graph = policy_population_to_rdf(source)
    reparsed = Graph().parse(data=graph.serialize(format="turtle"), format="turtle")
    report = validate_policy_ecology_rdf(reparsed)
    assert report.conforms
    assert report.population_digest == population_digest(source)
    assert rdf_to_policy_population(reparsed) == source


def test_member_level_value_tamper_is_refused() -> None:
    graph = policy_population_to_rdf(population())
    root = _root(graph)
    target = next(
        (s, o) for s, o in graph.subject_objects(RDF.value) if s != root and "planner:B" in str(o)
    )
    graph.remove((target[0], RDF.value, target[1]))
    graph.add((target[0], RDF.value, Literal(str(target[1]).replace("planner:B", "planner:Z"))))
    assert "REFUSED:POLICY_ECOLOGY_RDF_PROJECTION_MISMATCH" in _refused(graph)


def test_member_level_extent_tamper_is_refused() -> None:
    graph = policy_population_to_rdf(population())
    cell = next(iter(graph.subjects(DCTERMS.isPartOf, None)))
    (value,) = tuple(graph.objects(cell, RDF.value))
    graph.remove((cell, RDF.value, value))
    graph.add((cell, RDF.value, Literal("0.123456", datatype=XSD.decimal)))
    assert "REFUSED:POLICY_ECOLOGY_RDF_PROJECTION_MISMATCH" in _refused(graph)


def test_dropped_member_is_refused() -> None:
    graph = policy_population_to_rdf(population())
    root = _root(graph)
    dropped = next(iter(graph.objects(root, DCTERMS.hasPart)))
    graph.remove((root, DCTERMS.hasPart, dropped))
    for triple in list(graph.triples((dropped, None, None))):
        graph.remove(triple)
    assert "REFUSED:POLICY_ECOLOGY_RDF_PROJECTION_MISMATCH" in _refused(graph)


def test_injected_foreign_member_is_refused() -> None:
    graph = policy_population_to_rdf(population())
    foreign = URIRef("urn:attacker:phenotype:0")
    graph.add((foreign, RDF.type, PROV_ENTITY))
    graph.add((_root(graph), DCTERMS.hasPart, foreign))
    assert "REFUSED:POLICY_ECOLOGY_RDF_PROJECTION_MISMATCH" in _refused(graph)


def test_second_root_is_refused() -> None:
    graph = policy_population_to_rdf(population())
    other = PolicyPopulation(
        kind=PopulationKind.HOMOGENEOUS, members=(member("planner:C", 1.0, boldness=0.5),)
    )
    graph += policy_population_to_rdf(other)
    assert "REFUSED:POLICY_ECOLOGY_RDF_REQUIRES_ONE_ROOT" in _refused(graph)


@pytest.mark.parametrize(
    ("policy_ref", "evidence_ref"),
    [
        ("planner A", "https://arxiv.org/abs/2609.29423"),
        ("a<b>", "https://arxiv.org/abs/2609.29423"),
        ("no-scheme", "https://arxiv.org/abs/2609.29423"),
        ("planner:A", "ev ref"),
        ("planner:A", 'urn:x:"quoted"'),
    ],
)
def test_non_iri_refs_are_refused_at_projection(policy_ref: str, evidence_ref: str) -> None:
    source = PolicyPopulation(
        kind=PopulationKind.HOMOGENEOUS,
        members=(
            WeightedPhenotype(
                phenotype=PolicyPhenotype(policy_ref=policy_ref, evidence_refs=(evidence_ref,)),
                weight=1.0,
            ),
        ),
    )
    with pytest.raises(ValueError, match="REFUSED:POLICY_ECOLOGY_RDF_REF_NOT_IRI"):
        policy_population_to_rdf(source)


def test_projection_is_deterministic_and_order_canonical() -> None:
    left = policy_population_to_rdf(population())
    right = policy_population_to_rdf(population())
    assert set(left) == set(right)
    reordered = PolicyPopulation(
        kind=PopulationKind.ENGINEERED,
        members=(
            WeightedPhenotype(
                phenotype=PolicyPhenotype(
                    policy_ref="planner:A",
                    condition=StrategicCondition(values=(("exploration", 0.4), ("boldness", 0.1))),
                    evidence_refs=("https://arxiv.org/abs/2609.29423",),
                ),
                weight=1.0,
            ),
            population().members[1],
        ),
    )
    assert population_digest(reordered) == population_digest(population())
