from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "ggen" / "career-gym-pack"
LOCAL = "urn:gymact:careergym:"


def _graph() -> Graph:
    return Graph().parse(PACK / "ontology.ttl", format="turtle")


def _gate_rows(graph: Graph, name: str) -> list[tuple[object, ...]]:
    return [tuple(row) for row in graph.query((PACK / "gates" / name).read_text())]


def test_careergym_is_public_vocabulary_abox() -> None:
    graph = _graph()
    forbidden = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, RDFS.Class, RDF.Property}
    leaked_tbox = [
        term
        for term in graph.subjects(RDF.type, None)
        if str(term).startswith(LOCAL)
        and any((term, RDF.type, kind) in graph for kind in forbidden)
    ]
    local_predicates = {predicate for _, predicate, _ in graph if str(predicate).startswith(LOCAL)}
    assert leaked_tbox == []
    assert local_predicates == set()


@pytest.mark.parametrize(
    "gate",
    [
        "010_no_custom_tbox.rq",
        "020_profile_basis.rq",
        "030_ats_interop_basis.rq",
        "040_sensitive_unknowns.rq",
        "050_consequence_separation.rq",
    ],
)
def test_fortune5_ats_graph_passes_all_gates(gate: str) -> None:
    assert _gate_rows(_graph(), gate) == []


def test_gates_refuse_regressions() -> None:
    graph = _graph()
    graph.add((URIRef(f"{LOCAL}BrokenClass"), RDF.type, OWL.Class))
    assert _gate_rows(graph, "010_no_custom_tbox.rq")

    graph = _graph()
    graph.remove((URIRef(f"{LOCAL}atsCandidateProfile"), RDF.type, URIRef("https://schema.org/ProfilePage")))
    assert _gate_rows(graph, "030_ats_interop_basis.rq")

    graph = _graph()
    graph.remove((URIRef(f"{LOCAL}workAuthorization"), URIRef("http://purl.org/dc/terms/description"), None))
    assert _gate_rows(graph, "040_sensitive_unknowns.rq")

    graph = _graph()
    graph.remove((URIRef(f"{LOCAL}jobApplication"), URIRef("https://schema.org/actionStatus"), None))
    assert _gate_rows(graph, "050_consequence_separation.rq")


def test_enterprise_ats_projection_targets_exist_without_vendor_authority() -> None:
    graph = _graph()
    required = {
        "workdayProjection",
        "successFactorsProjection",
        "oracleProjection",
        "escoMapping",
        "onetMapping",
    }
    subjects = {str(s).removeprefix(LOCAL) for s in graph.subjects() if str(s).startswith(LOCAL)}
    assert required <= subjects
