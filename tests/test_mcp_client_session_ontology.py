from pathlib import Path

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import DCTERMS, PROV, SOSA

from gymact.gyms.mcp_client_session import (
    MCP_CALL_TOOL_CAPABILITY,
    MCP_LIST_TOOLS_CAPABILITY,
    McpClientSessionProvider,
)
from gymact.models import Consequence

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY = ROOT / "ggen" / "protocol-gym-pack" / "mcp-consumers.ttl"
CLIENT = URIRef("urn:gymact:mcp:consumer:client-session")
LIST = URIRef("urn:gymact:mcp:capability:list_tools")
CALL = URIRef("urn:gymact:mcp:capability:call_tool")
METHOD_LIST = URIRef("urn:gymact:mcp:method-tools-list")
METHOD_CALL = URIRef("urn:gymact:mcp:method-tools-call")
CONDITIONAL = URIRef("urn:gymact:mcp:ConditionalEffect")
READ = URIRef("urn:gymact:consequence:read")
DO = URIRef("urn:gymact:consequence:do")


def _graph() -> Graph:
    return Graph().parse(ONTOLOGY, format="turtle")


def test_mcp_client_capabilities_equal_ontology_exactly() -> None:
    graph = _graph()
    runtime = {
        MCP_LIST_TOOLS_CAPABILITY.iri: MCP_LIST_TOOLS_CAPABILITY,
        MCP_CALL_TOOL_CAPABILITY.iri: MCP_CALL_TOOL_CAPABILITY,
    }
    admitted = {
        str(subject)
        for subject in graph.subjects(RDF.type, SOSA.Procedure)
        if str(subject).startswith("urn:gymact:mcp:capability:")
    }
    assert set(runtime) == admitted == {str(LIST), str(CALL)}

    for iri, capability in runtime.items():
        subject = URIRef(iri)
        assert str(graph.value(subject, DCTERMS.identifier)) == capability.binding
        assert str(graph.value(subject, DCTERMS.title)) == capability.title
        expected = READ if capability.consequence is Consequence.READ else DO
        assert graph.value(subject, DCTERMS.type) == expected
        assert (subject, PROV.wasDerivedFrom, CLIENT) in graph


def test_list_tools_is_read_and_bound_to_tools_list() -> None:
    graph = _graph()
    assert MCP_LIST_TOOLS_CAPABILITY.consequence is Consequence.READ
    assert (LIST, DCTERMS.relation, METHOD_LIST) in graph


def test_call_tool_is_conservative_do_envelope_over_conditional_mcp_call() -> None:
    graph = _graph()
    assert MCP_CALL_TOOL_CAPABILITY.consequence is Consequence.DO
    assert (CALL, DCTERMS.relation, METHOD_CALL) in graph
    assert (CALL, DCTERMS.relation, CONDITIONAL) in graph


def test_mcp_client_session_provider_identity_is_stable() -> None:
    assert McpClientSessionProvider.name == "mcp-client-session"
