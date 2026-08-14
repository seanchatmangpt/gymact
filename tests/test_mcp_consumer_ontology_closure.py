from __future__ import annotations

import ast
from pathlib import Path

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import DCTERMS, PROV

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "gymact"
CONSUMERS = ROOT / "ggen" / "protocol-gym-pack" / "mcp-consumers.ttl"
CENTRAL = ROOT / "ggen" / "protocol-gym-pack" / "ontology.ttl"
CONSUMER_PREFIX = "urn:gymact:mcp:consumer:"
MCP_PREFIX = "urn:gymact:mcp:"
LOCAL_PREFIXES = (
    "urn:gymact:mcp:consumer:",
    "urn:gymact:mcp:capability:",
    "urn:gymact:mcp:role:",
)
MCP_IMPORT_ROOTS = {"fastmcp", "mcp"}


def _consumer_graph() -> Graph:
    return Graph().parse(CONSUMERS, format="turtle")


def _admitted_sources(graph: Graph) -> dict[URIRef, str]:
    admitted: dict[URIRef, str] = {}
    for subject in graph.subjects(RDF.type, PROV.Entity):
        if not str(subject).startswith(CONSUMER_PREFIX):
            continue
        sources = list(graph.objects(subject, DCTERMS.source))
        assert len(sources) == 1, f"{subject} must have exactly one dct:source"
        source = str(sources[0])
        assert subject not in admitted, f"duplicate MCP consumer entity: {subject}"
        admitted[subject] = source
    assert admitted, "MCP consumer ontology admitted no consumers"
    assert len(set(admitted.values())) == len(admitted), (
        "MCP consumer source paths must be unique"
    )
    return admitted


def _imports_mcp_transport(path: Path) -> bool:
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name.split(".", 1)[0] in MCP_IMPORT_ROOTS for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".", 1)[0] in MCP_IMPORT_ROOTS:
                return True
    return False


def _source_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_every_admitted_mcp_consumer_has_one_existing_source() -> None:
    graph = _consumer_graph()
    for source in _admitted_sources(graph).values():
        assert source.startswith("src/gymact/"), (
            f"MCP consumer escaped source boundary: {source}"
        )
        path = ROOT / source
        assert path.is_file(), f"admitted MCP consumer source does not exist: {source}"


def test_direct_mcp_imports_and_mcp_named_modules_are_ontology_admitted() -> None:
    graph = _consumer_graph()
    admitted = set(_admitted_sources(graph).values())
    python_files = tuple(SRC.rglob("*.py"))

    direct_imports = {
        _source_relative(path) for path in python_files if _imports_mcp_transport(path)
    }
    mcp_named = {
        _source_relative(path) for path in python_files if "mcp" in path.stem.lower()
    }
    discovered = direct_imports | mcp_named
    missing = discovered - admitted

    assert not missing, f"MCP_CONSUMER_NOT_ONTOLOGY_ADMITTED:{sorted(missing)}"


def test_consumer_mcp_relations_resolve_in_central_protocol_ontology() -> None:
    consumers = _consumer_graph()
    central = Graph().parse(CENTRAL, format="turtle")
    central_nodes = set(central.all_nodes())

    unresolved = {
        relation
        for relation in consumers.objects(None, DCTERMS.relation)
        if isinstance(relation, URIRef)
        and str(relation).startswith(MCP_PREFIX)
        and not str(relation).startswith(LOCAL_PREFIXES)
        and relation not in central_nodes
    }

    assert not unresolved, (
        f"MCP_CONSUMER_RELATION_UNRESOLVED:{sorted(map(str, unresolved))}"
    )


def test_client_session_consumer_is_exactly_source_bound() -> None:
    graph = _consumer_graph()
    client = URIRef("urn:gymact:mcp:consumer:client-session")
    sources = list(graph.objects(client, DCTERMS.source))

    assert len(sources) == 1
    assert str(sources[0]) == "src/gymact/gyms/mcp_client_session.py"
