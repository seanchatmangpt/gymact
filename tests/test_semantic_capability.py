from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph

from gymact.semantic import ProfileAuthority

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACK_ONTOLOGIES = (
    _REPO_ROOT / "ggen" / "gymact-bridge-pack" / "ontology.ttl",
    _REPO_ROOT / "ggen" / "multicloud-gym-pack" / "ontology.ttl",
)


def _graph(turtle: str) -> Graph:
    graph = Graph()
    graph.parse(data=turtle, format="turtle")
    return graph


def test_public_sosa_procedure_capability_conforms() -> None:
    data = _graph(
        """
        @prefix dct: <http://purl.org/dc/terms/> .
        @prefix sosa: <http://www.w3.org/ns/sosa/> .

        <urn:test:capability:set-value>
            a sosa:Procedure ;
            dct:title "Set value" ;
            dct:type <urn:gymact:consequence:do> .
        """
    )
    result = ProfileAuthority().validate_data(data)
    assert result.conforms, result.report_text
    assert result.custom_tbox_terms == ()


def test_capability_missing_consequence_is_rejected_by_real_shacl() -> None:
    data = _graph(
        """
        @prefix dct: <http://purl.org/dc/terms/> .
        @prefix sosa: <http://www.w3.org/ns/sosa/> .

        <urn:test:capability:incomplete>
            a sosa:Procedure ;
            dct:title "Incomplete capability" .
        """
    )
    result = ProfileAuthority().validate_data(data)
    assert result.conforms is False
    assert "consequence" in result.report_text.lower() or "dct:type" in result.report_text


def test_capability_with_unknown_consequence_is_rejected() -> None:
    data = _graph(
        """
        @prefix dct: <http://purl.org/dc/terms/> .
        @prefix sosa: <http://www.w3.org/ns/sosa/> .

        <urn:test:capability:unknown-consequence>
            a sosa:Procedure ;
            dct:title "Unknown consequence" ;
            dct:type <urn:test:consequence:maybe> .
        """
    )
    result = ProfileAuthority().validate_data(data)
    assert result.conforms is False


def test_extension_cannot_smuggle_custom_gymact_tbox() -> None:
    data = _graph(
        """
        @prefix owl: <http://www.w3.org/2002/07/owl#> .

        <urn:gymact:BadCustomClass> a owl:Class .
        """
    )
    result = ProfileAuthority().validate_data(data)
    assert result.conforms is False
    assert result.custom_tbox_terms == ("urn:gymact:BadCustomClass",)
    assert "CUSTOM_TBOX_REFUSED" in result.report_text


@pytest.mark.parametrize("ontology_path", _PACK_ONTOLOGIES, ids=lambda p: p.parent.name)
def test_ggen_pack_ontology_declares_zero_custom_tbox(ontology_path: Path) -> None:
    """Every ggen pack ontology.ttl must be pure ABox against urn:gymact: -- zero
    owl:Class/owl:*Property/rdfs:Class/rdf:Property individuals under the
    urn:gymact: prefix, checked with the same real admission logic that guards
    the packaged profile.ttl (test_extension_cannot_smuggle_custom_gymact_tbox
    above), not a separate/weaker check. Neither pack ontology is loaded by
    ProfileAuthority itself (which is hardcoded to gymact's own packaged
    profile), so nothing previously exercised this invariant against them."""
    graph = Graph()
    graph.parse(ontology_path, format="turtle")
    assert ProfileAuthority._custom_tbox_terms(graph) == ()
