"""Mechanical contract checks over canonical public-semantic graphs."""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import URIRef
from rdflib.namespace import RDF

from gymact.semantics.canonical_graph import CanonicalGraph
from gymact.semantics.rdf_source import ContractRefusal, SchemaRefusal, SourceDriftRefusal

DCT_IDENTIFIER = URIRef("http://purl.org/dc/terms/identifier")
PPLAN_PLAN = URIRef("http://purl.org/net/p-plan#Plan")
SOSA_PROCEDURE = URIRef("http://www.w3.org/ns/sosa/Procedure")
TD_ACTION_AFFORDANCE = URIRef("https://www.w3.org/2019/wot/td#ActionAffordance")
EXECUTABLE_PUBLIC_TYPES = frozenset({PPLAN_PLAN, SOSA_PROCEDURE, TD_ACTION_AFFORDANCE})


@dataclass(frozen=True)
class ExecutableSemanticTerm:
    iri: str
    rdf_types: tuple[str, ...]
    identifier: str | None
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class SemanticContract:
    expected_triple_count: int | None = None
    expected_source_count: int | None = None
    expected_digest: str | None = None
    required_iris: frozenset[str] = frozenset()
    required_predicates: frozenset[str] = frozenset()
    executable_iris: frozenset[str] | None = None


def executable_terms(snapshot: CanonicalGraph) -> tuple[ExecutableSemanticTerm, ...]:
    terms: list[ExecutableSemanticTerm] = []
    subjects = {
        subject
        for public_type in EXECUTABLE_PUBLIC_TYPES
        for subject in snapshot.graph.subjects(RDF.type, public_type)
        if isinstance(subject, URIRef)
    }
    for subject in sorted(subjects, key=str):
        identifiers = sorted(
            str(value) for value in snapshot.graph.objects(subject, DCT_IDENTIFIER)
        )
        if len(identifiers) > 1:
            raise ContractRefusal(f"identifier uniqueness violation: {subject}")
        types = tuple(
            sorted(
                str(type_)
                for type_ in snapshot.graph.objects(subject, RDF.type)
                if isinstance(type_, URIRef)
            )
        )
        terms.append(
            ExecutableSemanticTerm(
                iri=str(subject),
                rdf_types=types,
                identifier=identifiers[0] if identifiers else None,
                source_ids=snapshot.subject_sources.get(str(subject), ()),
            )
        )
    return tuple(terms)


def verify_contract(snapshot: CanonicalGraph, contract: SemanticContract) -> None:
    if (
        contract.expected_triple_count is not None
        and snapshot.triple_count != contract.expected_triple_count
    ):
        raise ContractRefusal(
            f"triple exact-count violation: expected {contract.expected_triple_count}, "
            f"observed {snapshot.triple_count}"
        )
    if (
        contract.expected_source_count is not None
        and len(snapshot.provenance) != contract.expected_source_count
    ):
        raise ContractRefusal(
            f"source exact-count violation: expected {contract.expected_source_count}, "
            f"observed {len(snapshot.provenance)}"
        )
    if contract.expected_digest is not None and snapshot.digest != contract.expected_digest:
        raise SourceDriftRefusal(
            f"canonical drift: expected {contract.expected_digest}, observed {snapshot.digest}"
        )

    graph_iris = {
        str(term)
        for triple in snapshot.graph
        for term in triple
        if isinstance(term, URIRef)
    }
    missing_iris = contract.required_iris - graph_iris
    if missing_iris:
        raise ContractRefusal(f"required subset absent: {sorted(missing_iris)!r}")

    predicates = {str(predicate) for _, predicate, _ in snapshot.graph}
    missing_predicates = contract.required_predicates - predicates
    if missing_predicates:
        raise SchemaRefusal(f"required predicates absent: {sorted(missing_predicates)!r}")

    if contract.executable_iris is not None:
        observed = {term.iri for term in executable_terms(snapshot)}
        if observed != contract.executable_iris:
            raise ContractRefusal(
                "executable exact-set violation: "
                f"expected={sorted(contract.executable_iris)!r} observed={sorted(observed)!r}"
            )
