from __future__ import annotations

import ast
from pathlib import Path

from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, PROV, SOSA

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "gymact" / "surfaces" / "fastmcp.py"
ONTOLOGY = ROOT / "ggen" / "gymact-bridge-pack" / "ontology.ttl"
BRIDGE = "urn:gymact:bridge:capability:"
READ = URIRef("urn:gymact:consequence:read")
DO = URIRef("urn:gymact:consequence:do")
MODERN_MCP = URIRef("urn:gymact:mcp:revision-2026-07-28")
CONDITIONAL_EFFECT = URIRef("urn:gymact:mcp:ConditionalEffect")

EXPECTED_READ = {
    "discover",
    "capabilities",
    "observe",
    "verify",
    "checkpoint",
    "probe_repo",
}
EXPECTED_DO = {"create_episode", "act", "restore", "teardown"}


def _decorator_is_mcp_tool(node: ast.expr) -> bool:
    target = node.func if isinstance(node, ast.Call) else node
    return isinstance(target, ast.Attribute) and target.attr == "tool"


def _source_tools() -> set[str]:
    tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_decorator_is_mcp_tool(decorator) for decorator in node.decorator_list)
    }


def _graph() -> Graph:
    return Graph().parse(ONTOLOGY, format="turtle")


def _ontology_tools(graph: Graph) -> dict[str, URIRef]:
    tools: dict[str, URIRef] = {}
    for subject in graph.subjects(RDF.type, SOSA.Procedure):
        if not str(subject).startswith(BRIDGE):
            continue
        identifier = graph.value(subject, DCTERMS.identifier)
        assert identifier is not None, f"{subject} lacks dct:identifier"
        name = str(identifier)
        assert name not in tools, f"duplicate FastMCP tool identifier: {name}"
        tools[name] = subject
    return tools


def test_fastmcp_tool_surface_equals_ontology_exactly() -> None:
    graph = _graph()
    observed = _source_tools()
    admitted = set(_ontology_tools(graph))

    assert observed == EXPECTED_READ | EXPECTED_DO
    assert admitted == observed
    assert len(admitted) == 10


def test_fastmcp_consequence_partition_is_complete_and_disjoint() -> None:
    graph = _graph()
    tools = _ontology_tools(graph)
    read = {name for name, subject in tools.items() if graph.value(subject, DCTERMS.type) == READ}
    do = {name for name, subject in tools.items() if graph.value(subject, DCTERMS.type) == DO}

    assert read == EXPECTED_READ
    assert do == EXPECTED_DO
    assert read.isdisjoint(do)
    assert read | do == set(tools)


def test_fastmcp_surface_is_bound_to_current_mcp_revision_and_exact_source() -> None:
    graph = _graph()
    surface = URIRef("urn:gymact:bridge:fastmcp-surface")
    sources = list(graph.objects(surface, DCTERMS.source))

    assert len(sources) == 1
    assert str(sources[0]) == "src/gymact/surfaces/fastmcp.py"
    assert (surface, DCTERMS.conformsTo, MODERN_MCP) in graph
    assert set(graph.objects(surface, DCTERMS.hasPart)) == set(_ontology_tools(graph).values())


def test_fastmcp_act_is_conditional_effect_and_authority_bounded() -> None:
    graph = _graph()
    act = URIRef(BRIDGE + "act")

    assert (act, DCTERMS.relation, CONDITIONAL_EFFECT) in graph
    assert graph.value(act, DCTERMS.type) == DO
    assert graph.value(act, DCTERMS.requires) is not None


def test_all_fastmcp_tools_are_provenance_bound_to_surface() -> None:
    graph = _graph()
    surface = URIRef("urn:gymact:bridge:fastmcp-surface")
    for subject in _ontology_tools(graph).values():
        assert (subject, PROV.wasDerivedFrom, surface) in graph
