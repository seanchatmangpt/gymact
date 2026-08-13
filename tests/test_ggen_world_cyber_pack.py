from __future__ import annotations

import re
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "ggen" / "world-cyber-gym-pack"
LOCAL = "urn:gymact:world-cyber:"
_TO = re.compile(r'^to: "([^"]+)"$', re.MULTILINE)


def graph() -> Graph:
    return Graph().parse(PACK / "ontology.ttl", format="turtle")


def test_public_ontology_abox_has_no_local_tbox_or_predicates() -> None:
    g = graph()
    forbidden = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, RDFS.Class, RDF.Property}
    assert [
        subject for subject in g.subjects(RDF.type, None)
        if str(subject).startswith(LOCAL) and any((subject, RDF.type, kind) in g for kind in forbidden)
    ] == []
    assert {predicate for _, predicate, _ in g if str(predicate).startswith(LOCAL)} == set()


def test_admitted_graph_passes_world_contract_gate() -> None:
    assert list(graph().query((PACK / "gates" / "010_world_contract.rq").read_text())) == []


def test_gate_refuses_non_synthetic_disturbance() -> None:
    g = graph()
    cap = URIRef(f"{LOCAL}cap:degrade-service")
    profile = URIRef(f"{LOCAL}profile:synthetic-only")
    conforms = URIRef("http://purl.org/dc/terms/conformsTo")
    g.remove((cap, conforms, profile))
    rows = list(g.query((PACK / "gates" / "010_world_contract.rq").read_text()))
    assert any(str(problem) == "disturbance-not-synthetic-only" for _, problem in rows)


def test_ggen_targets_are_static_cross_language_projections_only() -> None:
    targets = []
    for template in sorted((PACK / "templates").glob("*.tmpl")):
        match = _TO.search(template.read_text())
        assert match is not None
        targets.append(match.group(1))
    assert sorted(targets) == ["docs/compiled-reference.md", "src/lib.rs", "wit/gymact-world-cyber.wit"]
    assert all(not target.endswith(".py") for target in targets)
    combined = "\n".join(path.read_text() for path in (PACK / "templates").glob("*.tmpl"))
    assert "arbitrary-target" in combined
    assert "export catalog" in combined
