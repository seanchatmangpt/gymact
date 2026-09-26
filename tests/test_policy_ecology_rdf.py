from __future__ import annotations

from rdflib import Literal, URIRef
from rdflib.namespace import DCTERMS, RDF

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


def population() -> PolicyPopulation:
    return PolicyPopulation(
        kind=PopulationKind.ENGINEERED,
        members=(
            WeightedPhenotype(
                phenotype=PolicyPhenotype(
                    policy_ref="urn:planner:Astar",
                    condition=StrategicCondition(
                        values=(("exploration", 0.1), ("initiative", 0.9))
                    ),
                    evidence_refs=("urn:evidence:paper",),
                ),
                weight=1.0,
            ),
            WeightedPhenotype(
                phenotype=PolicyPhenotype(
                    policy_ref="urn:planner:Astar",
                    condition=StrategicCondition(
                        values=(("exploration", 0.9), ("initiative", 0.1))
                    ),
                    evidence_refs=("urn:evidence:paper",),
                ),
                weight=2.0,
            ),
        ),
    )


def test_rdf_projection_round_trips_losslessly_with_public_predicates() -> None:
    source = population()
    graph = policy_population_to_rdf(source)
    validation = validate_policy_ecology_rdf(graph)

    assert validation.conforms
    assert validation.custom_predicates == ()
    assert validation.population_digest == population_digest(source)
    assert rdf_to_policy_population(graph) == source


def test_rdf_projection_explicitly_carries_members_and_policy_identity() -> None:
    graph = policy_population_to_rdf(population())
    roots = list(graph.subjects(DCTERMS.conformsTo, URIRef("urn:gymact:profile:policy-ecology")))
    assert len(roots) == 1
    members = list(graph.objects(roots[0], DCTERMS.hasPart))
    assert len(members) == 2
    assert all(
        (member, RDF.type, URIRef("http://www.w3.org/ns/prov#Entity")) in graph
        for member in members
    )


def test_rdf_digest_tamper_is_refused_even_when_shape_still_conforms() -> None:
    graph = policy_population_to_rdf(population())
    root = next(graph.subjects(DCTERMS.conformsTo, URIRef("urn:gymact:profile:policy-ecology")))
    old = next(graph.objects(root, DCTERMS.identifier))
    graph.remove((root, DCTERMS.identifier, old))
    graph.add((root, DCTERMS.identifier, Literal("tampered")))

    validation = validate_policy_ecology_rdf(graph)
    assert not validation.conforms
    assert "REFUSED:POLICY_ECOLOGY_RDF_DIGEST_MISMATCH" in validation.report_text


def test_custom_private_predicate_fails_validation() -> None:
    graph = policy_population_to_rdf(population())
    root = next(graph.subjects(DCTERMS.conformsTo, URIRef("urn:gymact:profile:policy-ecology")))
    graph.add((root, URIRef("urn:gymact:privatePredicate"), Literal("no")))

    validation = validate_policy_ecology_rdf(graph)
    assert not validation.conforms
    assert validation.custom_predicates == ("urn:gymact:privatePredicate",)
