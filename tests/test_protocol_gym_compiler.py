from __future__ import annotations

from rdflib.namespace import RDF

from gymact.models import Consequence, Standing
from gymact.protocol_gym import (
    ProtocolKind,
    a2a_card_to_gym_spec,
    lsp_initialize_to_gym_spec,
    mcp_tools_to_gym_spec,
)
from gymact.protocol_gym_rdf import SOSA, protocol_gym_spec_to_rdf


def test_mcp_tools_compile_to_authority_gated_structural_gym() -> None:
    spec = mcp_tools_to_gym_spec(subject_id="weather", endpoint_ref="stdio:weather", source_digest="mcp-digest", tools=[{"name": "get_weather", "title": "Weather", "inputSchema": {"type": "object", "properties": {"city": {"type": "string"}}}, "annotations": {"readOnlyHint": True}}])
    assert spec.protocol is ProtocolKind.MCP
    assert spec.standing is Standing.STRUCTURAL
    assert len(spec.capabilities) == 1
    capability = spec.capabilities[0]
    assert capability.consequence is Consequence.DO
    assert capability.authority_required is True
    assert capability.input_schema["type"] == "object"


def test_a2a_agent_card_skills_compile_without_promoting_claims_to_truth() -> None:
    spec = a2a_card_to_gym_spec(source_digest="card-digest", card={"name": "planner", "version": "1.0.0", "supportedInterfaces": [{"url": "https://agent.example/a2a", "protocolBinding": "JSONRPC"}], "skills": [{"id": "plan", "name": "Plan work", "description": "Produces a plan"}]})
    assert spec.protocol is ProtocolKind.A2A
    assert spec.endpoint_ref == "https://agent.example/a2a"
    assert spec.capabilities[0].binding == "plan"
    assert spec.capabilities[0].consequence is Consequence.DO
    assert spec.capabilities[0].authority_required


def test_lsp_server_capabilities_split_queries_from_edit_candidates() -> None:
    spec = lsp_initialize_to_gym_spec(subject_id="rust-analyzer", endpoint_ref="stdio:rust-analyzer", source_digest="lsp-digest", initialize_result={"serverInfo": {"name": "rust-analyzer", "version": "x"}, "capabilities": {"hoverProvider": True, "definitionProvider": True, "renameProvider": True, "executeCommandProvider": {"commands": ["rust-analyzer.runSingle"]}}})
    by_binding = {item.binding: item for item in spec.capabilities}
    assert by_binding["textDocument/hover"].consequence is Consequence.READ
    assert not by_binding["textDocument/hover"].authority_required
    assert by_binding["textDocument/rename"].consequence is Consequence.DO
    assert by_binding["workspace/executeCommand"].authority_required


def test_protocol_gym_rdf_uses_public_sosa_procedure_projection() -> None:
    spec = mcp_tools_to_gym_spec(subject_id="subject", endpoint_ref="stdio:subject", source_digest="digest", tools=[{"name": "act", "inputSchema": {"type": "object"}}])
    graph = protocol_gym_spec_to_rdf(spec)
    capability = next(iter(graph.subjects(RDF.type, SOSA.Procedure)))
    assert str(capability) == spec.capabilities[0].semantic_id
