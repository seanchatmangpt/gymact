"""Chicago-style tests for the GymAct semantic profile.

Parses the real profile.ttl with rdflib and validates real data graphs against its
real SHACL shapes with pyshacl — no mocking of rdflib/pyshacl internals.
"""

from __future__ import annotations

from importlib import resources

from pyshacl import validate
from rdflib import RDF, Graph, Literal, Namespace, URIRef

GYMACT = Namespace("urn:gymact:")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
DCTERMS = Namespace("http://purl.org/dc/terms/")


def _load_shapes_graph() -> Graph:
    graph = Graph()
    ttl_path = resources.files("gymact.semantic").joinpath("profile.ttl")
    graph.parse(source=str(ttl_path), format="turtle")
    return graph


def test_profile_parses_and_declares_shape() -> None:
    """The bundled profile.ttl is valid Turtle and declares the capability shape."""
    graph = _load_shapes_graph()
    assert len(graph) > 0
    assert (GYMACT.CapabilityShape, RDF.type, URIRef("http://www.w3.org/ns/shacl#NodeShape")) in graph


def test_conformant_capability_passes_shacl() -> None:
    """A capability with a title and a declared consequence class conforms."""
    shapes_graph = _load_shapes_graph()
    data_graph = Graph()
    capability = URIRef("urn:gymact:example:read-cluster-state")
    data_graph.add((capability, RDF.type, SOSA.Procedure))
    data_graph.add((capability, DCTERMS.title, Literal("Read cluster state")))
    data_graph.add((capability, DCTERMS.type, GYMACT["consequence-read"]))

    conforms, _, report_text = validate(data_graph=data_graph, shacl_graph=shapes_graph, inference="none")

    assert conforms, report_text


def test_capability_missing_consequence_class_fails_shacl() -> None:
    """A capability with a title but no consequence class violates the shape."""
    shapes_graph = _load_shapes_graph()
    data_graph = Graph()
    capability = URIRef("urn:gymact:example:untyped-capability")
    data_graph.add((capability, RDF.type, SOSA.Procedure))
    data_graph.add((capability, DCTERMS.title, Literal("Untyped capability")))

    conforms, _, report_text = validate(data_graph=data_graph, shacl_graph=shapes_graph, inference="none")

    assert not conforms
    assert "consequence" in report_text.lower() or str(DCTERMS.type) in report_text
