"""Real pyshacl validation of the additive gym-algebra SHACL contract.

Mirrors tests/test_semantic_capability.py's pattern exactly: build a real
rdflib Graph from Turtle, validate it against the real packaged SHACL shapes
file with pyshacl.validate, and assert on the real conforms/report result --
no mocked validator, no hardcoded expected-verdict string.

This exercises src/gymact/ontology/gym_algebra.shacl.ttl directly (not
through gymact.semantic.ProfileAuthority, which is hardcoded to the separate
profile.shacl.ttl file) because that file is additive and deliberately kept
out of ProfileAuthority's existing bundle.
"""

from __future__ import annotations

from importlib.resources import as_file, files

from pyshacl import validate as shacl_validate
from rdflib import Graph

_PREFIXES = """
@prefix odrl: <http://www.w3.org/ns/odrl/2/> .
@prefix pplan: <http://purl.org/net/p-plan#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
"""


def _graph(turtle: str) -> Graph:
    graph = Graph()
    graph.parse(data=_PREFIXES + turtle, format="turtle")
    return graph


def _shapes() -> Graph:
    graph = Graph()
    with as_file(files("gymact.ontology").joinpath("gym_algebra.shacl.ttl")) as path:
        graph.parse(path, format="turtle")
    return graph


def _validate(data: Graph) -> tuple[bool, str]:
    conforms, _, report = shacl_validate(
        data,
        shacl_graph=_shapes(),
        inference="rdfs",
        abort_on_first=False,
        allow_infos=False,
        allow_warnings=False,
    )
    return bool(conforms), str(report)


def test_transition_with_all_required_refs_conforms() -> None:
    data = _graph(
        """
        <urn:test:transition:1>
            a prov:Entity ;
            prov:wasDerivedFrom <urn:test:worldstate:before> ;
            prov:wasGeneratedBy <urn:test:action:increment> ;
            odrl:target <urn:test:policy:allow-increment> ;
            prov:used <urn:test:observation:pre> .
        """
    )
    conforms, report = _validate(data)
    assert conforms, report


def test_transition_missing_authority_envelope_is_rejected() -> None:
    data = _graph(
        """
        <urn:test:transition:missing-authority>
            a prov:Entity ;
            prov:wasDerivedFrom <urn:test:worldstate:before> ;
            prov:wasGeneratedBy <urn:test:action:increment> ;
            prov:used <urn:test:observation:pre> .
        """
    )
    conforms, report = _validate(data)
    assert conforms is False
    assert "odrl" in report.lower() or "target" in report.lower()


def test_episode_with_transition_conforms() -> None:
    data = _graph(
        """
        <urn:test:episode:1>
            a prov:Activity ;
            prov:generated <urn:test:transition:1> .
        """
    )
    conforms, report = _validate(data)
    assert conforms, report


def test_episode_with_no_transition_is_rejected() -> None:
    data = _graph(
        """
        <urn:test:episode:empty>
            a prov:Activity .
        """
    )
    conforms, report = _validate(data)
    assert conforms is False
    assert "generated" in report.lower()


def test_composition_with_subgym_conforms() -> None:
    data = _graph(
        """
        <urn:test:composition:1>
            a pplan:Plan ;
            pplan:hasInputVar <urn:test:subgym:cube-counter> .
        """
    )
    conforms, report = _validate(data)
    assert conforms, report


def test_composition_with_no_subgym_is_rejected() -> None:
    data = _graph(
        """
        <urn:test:composition:empty>
            a pplan:Plan .
        """
    )
    conforms, report = _validate(data)
    assert conforms is False
    assert "subgym" in report.lower() or "hasinputvar" in report.lower()
