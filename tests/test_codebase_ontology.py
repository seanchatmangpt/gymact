"""Ontology-purity and shape tests for ggen/codebase-gym-pack/ontology.ttl.

Mirrors tests/test_semantic_capability.py's ontology-purity pattern (real
rdflib parse, real ProfileAuthority._custom_tbox_terms check -- zero custom
TBox under urn:gymact:) and tests/test_multicloud.py's real-parse-and-check
pattern for per-capability dct:title/dct:type shape. No provider module
(gymact.gyms.codebase) exists yet, so there is no CAPABILITY_REGISTRY to
diff against (unlike test_multicloud.py's registry-parity test) -- this file
checks the ontology is well-formed and pure on its own terms and records the
exact capability set for a future provider to match against.

Chicago-style: real rdflib parse of the real file on disk, real
ProfileAuthority (no mocking) -- no interaction-verifying test doubles.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import RDF, Graph, Namespace
from rdflib.namespace import DCTERMS

from gymact.semantic import ProfileAuthority

SOSA = Namespace("http://www.w3.org/ns/sosa/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

_ONTOLOGY_PATH = (
    Path(__file__).resolve().parents[1] / "ggen" / "codebase-gym-pack" / "ontology.ttl"
)

_EXPECTED_CAPABILITIES = {
    "inspect_tree": "urn:gymact:consequence:read",
    "read_file": "urn:gymact:consequence:read",
    "inspect_manifest": "urn:gymact:consequence:read",
    "inspect_git_diff": "urn:gymact:consequence:read",
    "apply_patch": "urn:gymact:consequence:do",
    "git_commit": "urn:gymact:consequence:do",
    "run_test": "urn:gymact:consequence:do",
    "run_build": "urn:gymact:consequence:do",
}


def _graph() -> Graph:
    graph = Graph()
    graph.parse(_ONTOLOGY_PATH, format="turtle")
    return graph


def test_ontology_file_exists_and_is_nonempty() -> None:
    assert _ONTOLOGY_PATH.is_file(), f"ontology file missing: {_ONTOLOGY_PATH}"
    assert _ONTOLOGY_PATH.stat().st_size > 0


def test_ontology_declares_zero_custom_tbox() -> None:
    """Same real admission logic that guards the packaged profile.ttl and the
    multicloud pack (test_semantic_capability.py's
    test_ggen_pack_ontology_declares_zero_custom_tbox) -- zero owl:Class/
    owl:*Property/rdfs:Class/rdf:Property individuals under urn:gymact:."""
    graph = _graph()
    assert ProfileAuthority._custom_tbox_terms(graph) == ()


def test_every_sosa_procedure_has_exactly_one_title_and_type() -> None:
    """Real parse-and-check mirroring test_multicloud.py's
    _ontology_procedures() shape assertions -- SHACL-shape-equivalent check
    run directly against the real graph."""
    graph = _graph()
    procedures = list(graph.subjects(RDF.type, SOSA.Procedure))
    assert len(procedures) == len(_EXPECTED_CAPABILITIES)

    found: dict[str, str] = {}
    for subject in procedures:
        titles = list(graph.objects(subject, DCTERMS.title))
        types = list(graph.objects(subject, DCTERMS.type))
        assert len(titles) == 1, f"{subject} must have exactly one dct:title, got {titles}"
        assert len(types) == 1, f"{subject} must have exactly one dct:type, got {types}"
        found[str(titles[0])] = str(types[0])

    assert found == _EXPECTED_CAPABILITIES


def test_capability_data_conforms_to_real_shacl_shape() -> None:
    """Each capability instance, in isolation, conforms to the real
    urn:gymact:shape:capability SHACL shape via the real ProfileAuthority
    validator -- the same authority test_semantic_capability.py exercises."""
    graph = _graph()
    result = ProfileAuthority().validate_data(graph)
    assert result.conforms, result.report_text


@pytest.mark.parametrize("title", sorted(_EXPECTED_CAPABILITIES))
def test_every_capability_is_a_skos_concept_with_broader(title: str) -> None:
    """Every capability is additionally typed skos:Concept and linked
    skos:broader into the pack's own operation-domain scheme, mirroring the
    multicloud pack's SKOS multi-typing pattern."""
    graph = _graph()
    matches = [
        subject
        for subject in graph.subjects(RDF.type, SOSA.Procedure)
        if (subject, DCTERMS.title, None) in graph
        and str(next(graph.objects(subject, DCTERMS.title))) == title
    ]
    assert len(matches) == 1
    subject = matches[0]
    assert (subject, RDF.type, SKOS.Concept) in graph
    broader = list(graph.objects(subject, SKOS.broader))
    assert len(broader) == 1
    assert str(broader[0]).startswith("urn:gymact:codebase:operation-domain:")
