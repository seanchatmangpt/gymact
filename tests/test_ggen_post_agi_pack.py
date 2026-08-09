from __future__ import annotations

import re
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "ggen" / "post-agi-crown-pack"
TEMPLATES = PACK / "templates"
ONTOLOGY = PACK / "ontology.ttl"
DCT = Namespace("http://purl.org/dc/terms/")
PROJECTION_TYPE = URIRef("urn:gymact:crown:concept:projection")
_TO = re.compile(r'^to: "([^"]+)"$', re.MULTILINE)


def _template_targets() -> tuple[str, ...]:
    targets: list[str] = []
    for template in sorted(TEMPLATES.glob("*.tmpl")):
        match = _TO.search(template.read_text(encoding="utf-8"))
        assert match is not None, f"missing to: frontmatter: {template}"
        targets.append(match.group(1))
    return tuple(targets)


def _ontology_targets() -> tuple[str, ...]:
    graph = Graph().parse(ONTOLOGY, format="turtle")
    targets = {
        str(path)
        for projection in graph.subjects(RDF.type, URIRef("http://www.w3.org/ns/prov#Entity"))
        if (projection, DCT.type, PROJECTION_TYPE) in graph
        for path in graph.objects(projection, DCT.identifier)
    }
    return tuple(sorted(targets))


def test_post_agi_pack_owns_at_least_ten_normal_outputs() -> None:
    targets = _template_targets()
    assert len(targets) >= 10
    assert len(targets) == len(set(targets))
    assert all("generated" not in target.lower() for target in targets)
    assert all((ROOT / target).is_file() for target in targets)


def test_post_agi_graph_and_templates_have_exact_output_parity() -> None:
    assert tuple(sorted(_template_targets())) == _ontology_targets()


def test_post_agi_graph_remains_public_vocabulary_abox() -> None:
    graph = Graph().parse(ONTOLOGY, format="turtle")
    forbidden_types = {
        URIRef("http://www.w3.org/2002/07/owl#Class"),
        URIRef("http://www.w3.org/2002/07/owl#ObjectProperty"),
        URIRef("http://www.w3.org/2002/07/owl#DatatypeProperty"),
        URIRef("http://www.w3.org/2000/01/rdf-schema#Class"),
    }
    local_subjects = {subject for subject in graph.subjects() if str(subject).startswith("urn:gymact:")}
    assert not any((subject, RDF.type, forbidden) in graph for subject in local_subjects for forbidden in forbidden_types)
