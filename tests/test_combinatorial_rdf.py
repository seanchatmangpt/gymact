from __future__ import annotations

from rdflib import URIRef

from gymact.combinatorial import (
    DecisionPhase,
    MorphismKind,
    MorphismRequirements,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
)
from gymact.combinatorial_rdf import (
    graph_to_rdf,
    query_do_frontier,
    rdf_to_graph,
    validate_possibility_rdf,
)


def graph_fixture() -> PossibilityGraph:
    return PossibilityGraph(
        objects=(
            PossibilityObject(
                object_id="observation",
                kind=PossibilityObjectKind.ADMITTED_OBSERVATION,
                semantic_ref="urn:observation:1",
                ontology_refs=("http://www.w3.org/ns/prov#Entity",),
            ),
            PossibilityObject(
                object_id="plan",
                kind=PossibilityObjectKind.PLAN,
                semantic_ref="urn:plan:1",
            ),
            PossibilityObject(
                object_id="effect",
                kind=PossibilityObjectKind.RECEIPT,
                semantic_ref="urn:receipt:1",
            ),
        ),
        morphisms=(
            PossibilityMorphism(
                morphism_id="construct",
                source_id="observation",
                target_id="plan",
                kind=MorphismKind.PLAN,
                phase=DecisionPhase.CONSTRUCT,
            ),
            PossibilityMorphism(
                morphism_id="do",
                source_id="plan",
                target_id="effect",
                kind=MorphismKind.ACTUATE,
                phase=DecisionPhase.DO,
                requirements=MorphismRequirements(execution_grant_required=True),
            ),
        ),
    )


def test_public_rdf_is_lossless_and_shacl_admitted() -> None:
    original = graph_fixture()
    rdf = graph_to_rdf(original)
    validation = validate_possibility_rdf(rdf)
    assert validation.conforms, validation.report_text
    assert validation.custom_predicates == ()
    restored = rdf_to_graph(rdf)
    assert restored == original
    assert restored.graph_digest == original.graph_digest


def test_do_frontier_is_queryable_without_application_graph_traversal() -> None:
    rdf = graph_to_rdf(graph_fixture())
    assert query_do_frontier(rdf) == ("do",)


def test_non_public_predicate_is_detected_instead_of_normalized_away() -> None:
    rdf = graph_to_rdf(graph_fixture())
    rdf.add(
        (
            URIRef("urn:gymact:possibility-object:bad"),
            URIRef("urn:gymact:predicate:custom"),
            URIRef("urn:value"),
        )
    )
    validation = validate_possibility_rdf(rdf)
    assert not validation.conforms
    assert validation.custom_predicates == ("urn:gymact:predicate:custom",)
