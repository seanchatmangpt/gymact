from pathlib import Path

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import DCTERMS, SKOS, SOSA

from gymact.models import Consequence
from gymact.protocol_gym import PROTOCOL_CAPABILITIES, ProtocolGymProvider, _SCHEMAS

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY = ROOT / "ggen" / "protocol-gym-pack" / "ontology.ttl"
READ = URIRef("urn:gymact:consequence:read")
DO = URIRef("urn:gymact:consequence:do")


def _graph() -> Graph:
    return Graph().parse(ONTOLOGY, format="turtle")


def test_protocol_catalog_equals_ontology_exactly() -> None:
    graph = _graph()
    admitted = {
        str(graph.value(subject, DCTERMS.identifier))
        for subject in graph.subjects(RDF.type, SKOS.Concept)
        if str(subject).startswith("urn:gymact:protocol:")
    }
    assert admitted == set(_SCHEMAS) == {"mcp", "a2a", "lsp"}


def test_protocol_fixture_capabilities_equal_ontology_exactly() -> None:
    graph = _graph()
    runtime = {capability.binding: capability for capability in PROTOCOL_CAPABILITIES}
    admitted = {
        str(graph.value(subject, DCTERMS.identifier)): subject
        for subject in graph.subjects(RDF.type, SOSA.Procedure)
        if str(subject).startswith("urn:gymact:protocol-gym:fixture:")
    }

    assert set(runtime) == set(admitted) == {"read", "do"}
    for binding, capability in runtime.items():
        subject = admitted[binding]
        expected = READ if capability.consequence is Consequence.READ else DO
        assert str(graph.value(subject, DCTERMS.title)) == capability.title
        assert graph.value(subject, DCTERMS.type) == expected


def test_protocol_fixture_read_do_partition_is_exact() -> None:
    runtime = {capability.binding: capability.consequence for capability in PROTOCOL_CAPABILITIES}
    assert runtime == {"read": Consequence.READ, "do": Consequence.DO}


def test_protocol_gym_provider_identity_is_stable() -> None:
    assert ProtocolGymProvider.name == "protocol"
