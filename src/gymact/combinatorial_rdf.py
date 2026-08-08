"""Public-ontology authority for Design for Combinatorial Maximum.

The Python PossibilityGraph is a runtime projection. This module gives the same graph
a lossless RDF representation using only public predicates/classes plus GymAct ABox
resource identities. GymAct URNs used for kinds/phases/reversal are explicit SKOS
concept individuals, never GymAct-owned RDF/OWL predicates or classes.
"""
from __future__ import annotations

import json
from typing import Any

from pyshacl import validate
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, SH, SKOS

from gymact.combinatorial import PossibilityGraph, PossibilityMorphism, PossibilityObject
from gymact.evidence import digest
from gymact.models import FrozenModel

_PROFILE = URIRef("urn:gymact:profile:combinatorial-maximum")
_EXECUTION_GRANT_CONCEPT = URIRef("urn:gymact:concept:execution-grant")


class PossibilityRDFValidation(FrozenModel):
    conforms: bool
    report_text: str
    triple_count: int
    custom_predicates: tuple[str, ...]


def _object_uri(object_id: str) -> URIRef:
    return URIRef(f"urn:gymact:possibility-object:{digest(object_id)}")


def _morphism_uri(morphism_id: str) -> URIRef:
    return URIRef(f"urn:gymact:possibility-morphism:{digest(morphism_id)}")


def _graph_uri(graph_digest: str) -> URIRef:
    return URIRef(f"urn:gymact:possibility-graph:{graph_digest}")


def _concept(category: str, value: str) -> URIRef:
    return URIRef(f"urn:gymact:concept:{category}:{value}")


def _json(value: dict[str, Any]) -> Literal:
    return Literal(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _declare_concept(graph: Graph, resource: URIRef, notation: str) -> None:
    graph.add((resource, RDF.type, SKOS.Concept))
    graph.add((resource, SKOS.notation, Literal(notation)))


def _project_object(graph: Graph, root: URIRef, item: PossibilityObject) -> None:
    resource = _object_uri(item.object_id)
    kind = _concept("object-kind", item.kind.value)
    _declare_concept(graph, kind, item.kind.value)
    graph.add((resource, RDF.type, PROV.Entity))
    graph.add((resource, PROV.specializationOf, URIRef(item.semantic_ref)))
    graph.add((resource, DCTERMS.identifier, Literal(item.object_id)))
    graph.add((resource, DCTERMS.type, kind))
    graph.add((resource, PROV.value, _json(item.model_dump(mode="json"))))
    graph.add((root, DCTERMS.hasPart, resource))
    if item.revision is not None:
        graph.add((resource, DCTERMS.hasVersion, Literal(item.revision)))
    for ontology_ref in item.ontology_refs:
        graph.add((resource, DCTERMS.conformsTo, URIRef(ontology_ref)))
    for evidence_ref in item.evidence_refs:
        graph.add((resource, DCTERMS.references, URIRef(evidence_ref)))


def _project_morphism(graph: Graph, root: URIRef, item: PossibilityMorphism) -> None:
    activity = _morphism_uri(item.morphism_id)
    kind = _concept("morphism-kind", item.kind.value)
    phase = _concept("decision-phase", item.phase.value)
    reversal = _concept("reversal", item.reversal.value)
    _declare_concept(graph, kind, item.kind.value)
    _declare_concept(graph, phase, item.phase.value)
    _declare_concept(graph, reversal, item.reversal.value)
    graph.add((activity, RDF.type, PROV.Activity))
    graph.add((activity, DCTERMS.identifier, Literal(item.morphism_id)))
    graph.add((activity, DCTERMS.type, kind))
    graph.add((activity, DCTERMS.type, phase))
    graph.add((activity, DCTERMS.type, reversal))
    graph.add((activity, SKOS.notation, Literal(item.phase.value)))
    graph.add((activity, PROV.used, _object_uri(item.source_id)))
    graph.add((activity, PROV.generated, _object_uri(item.target_id)))
    graph.add((activity, PROV.value, _json(item.model_dump(mode="json"))))
    graph.add((root, DCTERMS.hasPart, activity))
    required = item.requirements
    for required_ref in (
        *required.capability_refs,
        *required.policy_refs,
        *required.evidence_refs,
    ):
        graph.add((activity, DCTERMS.requires, URIRef(required_ref)))
    if required.required_revision is not None:
        graph.add((activity, DCTERMS.hasVersion, Literal(required.required_revision)))
    if required.execution_grant_required:
        _declare_concept(graph, _EXECUTION_GRANT_CONCEPT, "execution-grant")
        graph.add((activity, DCTERMS.requires, _EXECUTION_GRANT_CONCEPT))
    for evidence_ref in item.evidence_refs:
        graph.add((activity, DCTERMS.references, URIRef(evidence_ref)))


def graph_to_rdf(value: PossibilityGraph) -> Graph:
    """Project a possibility graph into public PROV/DCTERMS/SKOS relations."""
    graph = Graph()
    root = _graph_uri(value.graph_digest)
    graph.add((root, RDF.type, PROV.Entity))
    graph.add((root, DCTERMS.identifier, Literal(value.graph_digest)))
    graph.add((root, DCTERMS.type, _PROFILE))
    _declare_concept(graph, _PROFILE, "combinatorial-maximum")
    for item in value.objects:
        _project_object(graph, root, item)
    for item in value.morphisms:
        _project_morphism(graph, root, item)
    return graph


def rdf_to_graph(graph: Graph, *, graph_digest: str | None = None) -> PossibilityGraph:
    """Reconstruct the typed runtime projection without inventing semantics."""
    roots = tuple(subject for subject in graph.subjects(DCTERMS.type, _PROFILE))
    if graph_digest is not None:
        expected = _graph_uri(graph_digest)
        if expected not in roots:
            raise ValueError("POSSIBILITY_RDF_GRAPH_IDENTITY_MISMATCH")
        root = expected
    elif len(roots) == 1:
        root = roots[0]
    else:
        raise ValueError("POSSIBILITY_RDF_GRAPH_ROOT_AMBIGUOUS")

    objects: list[PossibilityObject] = []
    morphisms: list[PossibilityMorphism] = []
    for part in graph.objects(root, DCTERMS.hasPart):
        raw = graph.value(part, PROV.value)
        if raw is None:
            raise ValueError("POSSIBILITY_RDF_PART_MISSING_PROV_VALUE")
        payload = json.loads(str(raw))
        if (part, RDF.type, PROV.Activity) in graph:
            morphisms.append(PossibilityMorphism.model_validate(payload))
        elif (part, RDF.type, PROV.Entity) in graph:
            objects.append(PossibilityObject.model_validate(payload))
        else:
            raise ValueError("POSSIBILITY_RDF_PART_TYPE_UNSUPPORTED")
    value = PossibilityGraph(objects=tuple(objects), morphisms=tuple(morphisms))
    recorded = graph.value(root, DCTERMS.identifier)
    if recorded is None or str(recorded) != value.graph_digest:
        raise ValueError("POSSIBILITY_RDF_CONTENT_DIGEST_MISMATCH")
    return value


def possibility_shapes() -> Graph:
    """SHACL admission for public graph structure; shape URNs are ABox resources."""
    shapes = Graph()
    object_shape = URIRef("urn:gymact:shape:possibility-object")
    activity_shape = URIRef("urn:gymact:shape:possibility-morphism")

    shapes.add((object_shape, RDF.type, SH.NodeShape))
    shapes.add((object_shape, SH.targetSubjectsOf, PROV.specializationOf))
    for index, (path, minimum, maximum) in enumerate(
        (
            (DCTERMS.identifier, 1, 1),
            (DCTERMS.type, 1, None),
            (PROV.value, 1, 1),
            (PROV.specializationOf, 1, 1),
        )
    ):
        prop = URIRef(f"urn:gymact:shape:possibility-object-property:{index}")
        shapes.add((object_shape, SH.property, prop))
        shapes.add((prop, SH.path, path))
        shapes.add((prop, SH.minCount, Literal(minimum)))
        if maximum is not None:
            shapes.add((prop, SH.maxCount, Literal(maximum)))

    shapes.add((activity_shape, RDF.type, SH.NodeShape))
    shapes.add((activity_shape, SH.targetClass, PROV.Activity))
    for index, (path, minimum, maximum) in enumerate(
        (
            (DCTERMS.identifier, 1, 1),
            (DCTERMS.type, 3, None),
            (SKOS.notation, 1, 1),
            (PROV.used, 1, 1),
            (PROV.generated, 1, 1),
            (PROV.value, 1, 1),
        )
    ):
        prop = URIRef(f"urn:gymact:shape:possibility-morphism-property:{index}")
        shapes.add((activity_shape, SH.property, prop))
        shapes.add((prop, SH.path, path))
        shapes.add((prop, SH.minCount, Literal(minimum)))
        if maximum is not None:
            shapes.add((prop, SH.maxCount, Literal(maximum)))
    return shapes


def validate_possibility_rdf(graph: Graph) -> PossibilityRDFValidation:
    conforms, _, report = validate(
        data_graph=graph,
        shacl_graph=possibility_shapes(),
        inference="none",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )
    public_predicate_namespaces = (
        str(RDF),
        str(PROV),
        str(DCTERMS),
        str(SKOS),
    )
    custom = tuple(
        sorted(
            {
                str(predicate)
                for _, predicate, _ in graph
                if not str(predicate).startswith(public_predicate_namespaces)
            }
        )
    )
    return PossibilityRDFValidation(
        conforms=bool(conforms) and not custom,
        report_text=str(report),
        triple_count=len(graph),
        custom_predicates=custom,
    )


def query_do_frontier(graph: Graph) -> tuple[str, ...]:
    """Indexed-query-friendly retrieval of DO morphism identities from public RDF."""
    query = f"""
    SELECT ?id WHERE {{
      ?activity a <{PROV.Activity}> ;
                <{SKOS.notation}> "DO" ;
                <{DCTERMS.identifier}> ?id .
    }} ORDER BY ?id
    """
    return tuple(str(row.id) for row in graph.query(query))
