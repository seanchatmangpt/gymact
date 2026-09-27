"""Lossless public-ontology projection for policy ecology.

The Python models are runtime projections. This module projects a policy
population as PROV-O/DCTERMS/SKOS RDF while keeping GymAct-owned URNs confined
to resource identities. No GymAct-private RDF predicate or class is introduced.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, SH, SKOS, XSD

from gymact.evidence import canonical_bytes, digest
from gymact.models import FrozenModel
from gymact.policy_ecology import PolicyPopulation

PROV = Namespace("http://www.w3.org/ns/prov#")

_PROFILE = URIRef("urn:gymact:profile:policy-ecology")

# RFC 3987 scheme followed by no character that rdflib refuses to serialize
# (whitespace, controls, <>"{}|\\^`). Refs that fail this cannot round-trip
# through Turtle/N-Triples, so projection refuses them instead of emitting a
# graph that breaks at serialization time.
_IRI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:[^\s<>\"{}|\\^`\x00-\x1f\x7f]+$")


def _iri(ref: str, role: str) -> URIRef:
    if not _IRI.match(ref):
        raise ValueError(f"REFUSED:POLICY_ECOLOGY_RDF_REF_NOT_IRI:{role}:{ref!r}")
    return URIRef(ref)


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


def _root_uri(population: PolicyPopulation, pop_digest: str | None = None) -> URIRef:
    return URIRef(f"urn:gymact:policy-population:{pop_digest or population_digest(population)}")


def _member_uri(pop_digest: str, index: int) -> URIRef:
    return URIRef(f"urn:gymact:policy-phenotype:{pop_digest}:{index}")


@lru_cache(maxsize=4096)
def _axis_concept(axis_id: str) -> URIRef:
    return URIRef(f"urn:gymact:temperament-axis:{digest({'axis_id': axis_id})}")


def _condition_cell(member: URIRef, axis_id: str) -> URIRef:
    return URIRef(f"{member}:axis:{digest({'axis_id': axis_id})}")


def _exact_decimal(value: float) -> Literal:
    """xsd:decimal literal carrying the float's shortest round-trip digits.

    xsd:double is avoided on purpose: rdflib's Turtle serializer rewrites
    doubles as "%e" (about 7 significant digits), which loses information.
    A positional xsd:decimal lexical form is written verbatim by every
    rdflib serializer, and float(Decimal(lexical)) == value exactly.
    """
    text = format(Decimal(repr(value)), "f")
    if "." not in text:
        text = f"{text}.0"
    return Literal(text, datatype=XSD.decimal, normalize=False)


_NUMERIC_DATATYPES = frozenset({XSD.decimal, XSD.double, XSD.float, XSD.integer, XSD.int, XSD.long})


def _term_key(term: Any) -> Any:
    """Compare numeric literals by datatype and exact value, other terms by identity.

    Parsers may re-lexicalize a numeric literal (e.g. 0.0000001 -> 1E-7), so
    the whole-graph binding compares numbers by their exact decimal value
    instead of their lexical form. Any change of value or datatype is still a
    mismatch.
    """
    if isinstance(term, Literal) and term.datatype in _NUMERIC_DATATYPES:
        try:
            return ("number", str(term.datatype), Decimal(str(term)).normalize())
        except InvalidOperation:
            return term
    return term


def _graph_key(graph: Graph) -> frozenset[tuple[Any, Any, Any]]:
    return frozenset(
        (_term_key(subject), _term_key(predicate), _term_key(obj))
        for subject, predicate, obj in graph
    )


def policy_population_to_rdf(population: PolicyPopulation) -> Graph:
    """Project one population to RDF without changing its standing or authority."""
    graph = Graph()
    graph.bind("prov", PROV)
    graph.bind("dct", DCTERMS)
    graph.bind("rdf", RDF)
    graph.bind("skos", SKOS)

    # One canonical dump and one digest per projection: the digest was
    # previously recomputed for every member URI (O(n^2) in member count).
    dump = _population_dump(population)
    encoded = canonical_bytes(dump).decode("utf-8")
    pop_digest = digest(dump)
    root = _root_uri(population, pop_digest)

    graph.add((root, RDF.type, PROV.Entity))
    graph.add((root, DCTERMS.conformsTo, _PROFILE))
    graph.add((root, DCTERMS.identifier, Literal(pop_digest)))
    graph.add((root, DCTERMS.type, Literal(population.kind.value)))
    graph.add((root, RDF.value, Literal(encoded)))

    for index, member in enumerate(population.members):
        resource = _member_uri(pop_digest, index)
        graph.add((resource, RDF.type, PROV.Entity))
        graph.add((resource, DCTERMS.type, Literal("policy_phenotype")))
        graph.add((resource, DCTERMS.identifier, Literal(str(index))))
        graph.add((root, DCTERMS.hasPart, resource))
        graph.add(
            (resource, PROV.specializationOf, _iri(member.phenotype.policy_ref, "policy_ref"))
        )
        graph.add(
            (
                resource,
                RDF.value,
                Literal(canonical_bytes(member.model_dump(mode="json")).decode("utf-8")),
            )
        )
        for evidence_ref in member.phenotype.evidence_refs:
            graph.add((resource, PROV.wasDerivedFrom, _iri(evidence_ref, "evidence_ref")))

        # One cell per (member, axis): the cell names its axis and carries its
        # value, so the axis-to-value pairing is readable from the triples
        # alone and two axes with equal values stay distinct.
        for axis_id, value in member.phenotype.condition.values:
            concept = _axis_concept(axis_id)
            cell = _condition_cell(resource, axis_id)
            graph.add((concept, RDF.type, SKOS.Concept))
            graph.add((concept, SKOS.notation, Literal(axis_id)))
            graph.add((cell, DCTERMS.isPartOf, resource))
            graph.add((cell, DCTERMS.subject, concept))
            graph.add((cell, RDF.value, _exact_decimal(value)))

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
        prop = URIRef(f"urn:gymact:shape:policy-population:{digest(str(predicate))}")
        shape.add((root_shape, SH.property, prop))
        shape.add((prop, SH.path, predicate))
        shape.add((prop, SH.minCount, Literal(minimum)))
        if maximum is not None:
            shape.add((prop, SH.maxCount, Literal(maximum)))
    return shape


def _allowed_predicate(predicate: URIRef) -> bool:
    value = str(predicate)
    return (
        value.startswith(str(RDF))
        or value.startswith(str(DCTERMS))
        or value.startswith(str(PROV))
        or value.startswith(str(SKOS))
    )


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
    if root != _root_uri(population, expected):
        raise ValueError("REFUSED:POLICY_ECOLOGY_RDF_ROOT_IDENTITY_MISMATCH")
    # The root digest binds only the root's canonical value. Bind every other
    # triple too: the admitted graph must be exactly the projection of the
    # population it reconstructs, so tampering, dropping, or injecting a
    # member-level triple is refused rather than silently ignored.
    if _graph_key(graph) != _graph_key(policy_population_to_rdf(population)):
        raise ValueError("REFUSED:POLICY_ECOLOGY_RDF_PROJECTION_MISMATCH")
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
        population_digest=(population_digest(reconstructed) if reconstructed is not None else None),
    )
