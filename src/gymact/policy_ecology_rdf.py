"""Lossless public-ontology projection for policy ecology.

The Python models are runtime projections. This module projects a policy
population as PROV-O/DCTERMS/SKOS RDF while keeping GymAct-owned URNs confined
to resource identities. No GymAct-private RDF predicate or class is introduced.
"""

from __future__ import annotations

import json
from typing import Any

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, SH, SKOS

from gymact.evidence import canonical_bytes, digest
from gymact.models import FrozenModel
from gymact.policy_ecology import PolicyPopulation

PROV = Namespace("http://www.w3.org/ns/prov#")

_PROFILE = URIRef("urn:gymact:profile:policy-ecology")


class PolicyEcologyRDFValidation(FrozenModel):
    conforms: bool
    report_text: str
    triple_count: int
    custom_predicates: tuple[str, ...]
    population_digest: str | None = None


def _population_dump(population: PolicyPopulation) -> dict[str, Any]:
    return population.model_dump(mode="json")


def population_digest(population: PolicyPopulation) -> str:
    return digest(_population_dump(population))


def _root_uri(population: PolicyPopulation) -> URIRef:
    return URIRef(f"urn:gymact:policy-population:{population_digest(population)}")


def _member_uri(population: PolicyPopulation, index: int) -> URIRef:
    return URIRef(
        f"urn:gymact:policy-phenotype:{population_digest(population)}:{index}"
    )


def policy_population_to_rdf(population: PolicyPopulation) -> Graph:
    """Project one population to RDF without changing its standing or authority."""
    graph = Graph()
    graph.bind("prov", PROV)
    graph.bind("dct", DCTERMS)
    graph.bind("rdf", RDF)
    graph.bind("skos", SKOS)

    root = _root_uri(population)
    encoded = canonical_bytes(_population_dump(population)).decode("utf-8")
    pop_digest = population_digest(population)

    graph.add((root, RDF.type, PROV.Entity))
    graph.add((root, DCTERMS.conformsTo, _PROFILE))
    graph.add((root, DCTERMS.identifier, Literal(pop_digest)))
    graph.add((root, DCTERMS.type, Literal(population.kind.value)))
    graph.add((root, RDF.value, Literal(encoded)))

    for index, member in enumerate(population.members):
        resource = _member_uri(population, index)
        graph.add((resource, RDF.type, PROV.Entity))
        graph.add((resource, DCTERMS.type, Literal("policy_phenotype")))
        graph.add((resource, DCTERMS.identifier, Literal(str(index))))
        graph.add((root, DCTERMS.hasPart, resource))
        graph.add((resource, PROV.specializationOf, URIRef(member.phenotype.policy_ref)))
        graph.add(
            (
                resource,
                RDF.value,
                Literal(
                    canonical_bytes(member.model_dump(mode="json")).decode("utf-8")
                ),
            )
        )
        for evidence_ref in member.phenotype.evidence_refs:
            graph.add((resource, PROV.wasDerivedFrom, URIRef(evidence_ref)))

        for axis_id, value in member.phenotype.condition.values:
            concept = URIRef(
                f"urn:gymact:temperament-axis:{digest({'axis_id': axis_id})}"
            )
            graph.add((concept, RDF.type, SKOS.Concept))
            graph.add((concept, SKOS.notation, Literal(axis_id)))
            graph.add((resource, DCTERMS.subject, concept))
            graph.add((resource, DCTERMS.extent, Literal(value)))

    return graph


def _shape_graph() -> Graph:
    shape = Graph()
    root_shape = URIRef("urn:gymact:shape:policy-population")
    shape.add((root_shape, RDF.type, SH.NodeShape))
    shape.add((root_shape, SH.targetSubjectsOf, DCTERMS.conformsTo))

    for predicate, minimum, maximum in (
        (DCTERMS.identifier, 1, 1),
        (DCTERMS.type, 1, 1),
        (RDF.value, 1, 1),
        (DCTERMS.hasPart, 1, None),
    ):
        prop = URIRef(
            f"urn:gymact:shape:policy-population:{digest(str(predicate))}"
        )
        shape.add((root_shape, SH.property, prop))
        shape.add((prop, SH.path, predicate))
        shape.add((prop, SH.minCount, Literal(minimum)))
        if maximum is not None:
            shape.add((prop, SH.maxCount, Literal(maximum)))
    return shape


def _allowed_predicate(predicate: URIRef) -> bool:
    value = str(predicate)
    return value.startswith(str(RDF)) or value.startswith(str(DCTERMS)) or value.startswith(
        str(PROV)
    ) or value.startswith(str(SKOS))


def _population_roots(graph: Graph) -> tuple[URIRef, ...]:
    return tuple(
        subject
        for subject in graph.subjects(DCTERMS.conformsTo, _PROFILE)
        if isinstance(subject, URIRef)
    )


def rdf_to_policy_population(graph: Graph) -> PolicyPopulation:
    """Reconstruct the exact population from its canonical RDF value."""
    roots = _population_roots(graph)
    if len(roots) != 1:
        raise ValueError("REFUSED:POLICY_ECOLOGY_RDF_REQUIRES_ONE_ROOT")
    root = roots[0]

    values = tuple(graph.objects(root, RDF.value))
    identifiers = tuple(graph.objects(root, DCTERMS.identifier))
    if len(values) != 1 or len(identifiers) != 1:
        raise ValueError("REFUSED:POLICY_ECOLOGY_RDF_ROOT_CARDINALITY")

    try:
        raw = json.loads(str(values[0]))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("REFUSED:POLICY_ECOLOGY_RDF_VALUE_INVALID") from exc

    population = PolicyPopulation.model_validate(raw)
    expected = population_digest(population)
    if str(identifiers[0]) != expected:
        raise ValueError("REFUSED:POLICY_ECOLOGY_RDF_DIGEST_MISMATCH")
    if root != _root_uri(population):
        raise ValueError("REFUSED:POLICY_ECOLOGY_RDF_ROOT_IDENTITY_MISMATCH")
    return population


def validate_policy_ecology_rdf(graph: Graph) -> PolicyEcologyRDFValidation:
    """Run SHACL plus an independent lossless reconstruction/digest check."""
    custom = tuple(
        sorted(
            {
                str(predicate)
                for _, predicate, _ in graph
                if isinstance(predicate, URIRef) and not _allowed_predicate(predicate)
            }
        )
    )

    conforms, _report_graph, report_text = validate(
        graph,
        shacl_graph=_shape_graph(),
        inference="none",
        abort_on_first=False,
        allow_infos=False,
        allow_warnings=False,
    )

    reconstructed: PolicyPopulation | None = None
    reconstruction_error: str | None = None
    try:
        reconstructed = rdf_to_policy_population(graph)
    except ValueError as exc:
        reconstruction_error = str(exc)

    if custom:
        conforms = False
        reconstruction_error = reconstruction_error or "REFUSED:CUSTOM_RDF_PREDICATE"

    text = str(report_text)
    if reconstruction_error is not None:
        text = f"{text}\n{reconstruction_error}"

    return PolicyEcologyRDFValidation(
        conforms=bool(conforms) and reconstructed is not None and not custom,
        report_text=text,
        triple_count=len(graph),
        custom_predicates=custom,
        population_digest=(
            population_digest(reconstructed) if reconstructed is not None else None
        ),
    )
