#!/usr/bin/env python3
"""Manufacture protocol-gym's MCP projection from an ABox-only graph.

This is a bounded migration tool for the current protocol-gym pack. It removes
local schema assertions (RDFS/OWL class/property/domain/range/subclass facts)
while preserving every protocol instance fact queried by the existing MCP
surface courts. It then regenerates the Rust MCP surface from that admitted
graph. The script never executes an MCP tool or obtains DO authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import Graph, Namespace, RDF, RDFS, SKOS
from rdflib.namespace import OWL

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ggen" / "protocol-gym-pack" / "ontology.ttl"
RUST = ROOT / "rust" / "protocol_gym" / "src" / "mcp_surface.rs"
LIB = ROOT / "rust" / "protocol_gym" / "src" / "lib.rs"

MCP = Namespace("urn:gymact:mcp:")
DCT = Namespace("http://purl.org/dc/terms/")

_SCHEMA_TYPES = {
    RDFS.Class,
    OWL.Class,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    RDF.Property,
}
_SCHEMA_PREDICATES = {RDFS.domain, RDFS.range, RDFS.subClassOf}


def _is_local(term: object) -> bool:
    return str(term).startswith(str(MCP))


def _rust(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _bool(value: object) -> str:
    return "true" if str(value).lower() in {"true", "1"} else "false"


def migrate_aabox(graph: Graph) -> Graph:
    """Remove only local TBox assertions; retain the executable ABox graph."""
    labels: dict[object, object] = {}
    for subject, _, label in graph.triples((None, RDFS.label, None)):
        if _is_local(subject):
            labels[subject] = label

    for triple in tuple(graph):
        subject, predicate, obj = triple
        if not _is_local(subject):
            continue
        if predicate == RDF.type and obj in _SCHEMA_TYPES:
            graph.remove(triple)
        elif predicate in _SCHEMA_PREDICATES:
            graph.remove(triple)
        elif predicate == RDFS.label:
            graph.remove(triple)

    # Vocabulary identities remain data: SKOS concepts with labels. They are
    # not asserted as RDFS/OWL classes and therefore cannot manufacture schema
    # authority, while existing protocol instance facts remain addressable.
    for subject, label in labels.items():
        graph.add((subject, RDF.type, SKOS.Concept))
        graph.add((subject, SKOS.prefLabel, label))

    return graph


def _rows(graph: Graph, query: str) -> list[dict[str, object]]:
    result = []
    for row in graph.query(query):
        result.append({str(var): value for var, value in row.asdict().items()})
    return result


def generate_rust(graph: Graph) -> str:
    revision = _rows(
        graph,
        """
        PREFIX mcp: <urn:gymact:mcp:>
        SELECT ?version WHERE { mcp:revision-2026-07-28 mcp:protocolVersion ?version . }
        """,
    )
    core = _rows(
        graph,
        """
        PREFIX mcp: <urn:gymact:mcp:>
        PREFIX dct: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?name ?facet_id ?lifecycle_label ?kind_label ?direction_label ?invocation_label ?control_label ?consequence_label WHERE {
          ?method a mcp:Method ; mcp:methodName ?name ; mcp:facet ?facet ;
                  mcp:lifecycle ?lifecycle ; mcp:messageKind ?kind ;
                  mcp:direction ?direction ; mcp:invocationMode ?invocation ;
                  mcp:controlMode ?control ; mcp:consequence ?consequence ;
                  mcp:inRevision mcp:revision-2026-07-28 .
          ?facet dct:identifier ?facet_id .
          ?lifecycle skos:prefLabel ?lifecycle_label .
          ?kind skos:prefLabel ?kind_label .
          ?direction skos:prefLabel ?direction_label .
          ?invocation skos:prefLabel ?invocation_label .
          ?control skos:prefLabel ?control_label .
          ?consequence skos:prefLabel ?consequence_label .
        } ORDER BY ?name
        """,
    )
    extension = _rows(
        graph,
        """
        PREFIX mcp: <urn:gymact:mcp:>
        PREFIX dct: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?name ?facet_id ?extension_id ?lifecycle_label ?consequence_label WHERE {
          ?method a mcp:Method ; mcp:methodName ?name ; mcp:facet ?facet ;
                  mcp:extension ?extension ; mcp:lifecycle ?lifecycle ;
                  mcp:consequence ?consequence .
          ?facet dct:identifier ?facet_id .
          ?extension mcp:extensionId ?extension_id .
          ?lifecycle skos:prefLabel ?lifecycle_label .
          ?consequence skos:prefLabel ?consequence_label .
        } ORDER BY ?extension_id ?name
        """,
    )
    capabilities = _rows(
        graph,
        """
        PREFIX mcp: <urn:gymact:mcp:>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?side ?key ?lifecycle_label WHERE {
          ?capability a mcp:Capability ; mcp:capabilitySide ?side ;
                      mcp:capabilityKey ?key ; mcp:lifecycle ?lifecycle .
          ?lifecycle skos:prefLabel ?lifecycle_label .
        } ORDER BY ?side ?key
        """,
    )
    metadata = _rows(
        graph,
        """
        PREFIX mcp: <urn:gymact:mcp:>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?key ?required ?lifecycle_label WHERE {
          ?field a mcp:MetadataField ; mcp:metaKey ?key ;
                 mcp:required ?required ; mcp:lifecycle ?lifecycle .
          ?lifecycle skos:prefLabel ?lifecycle_label .
        } ORDER BY ?key
        """,
    )
    transports = _rows(
        graph,
        """
        PREFIX mcp: <urn:gymact:mcp:>
        PREFIX dct: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?id ?lifecycle_label ?compatibility_only WHERE {
          ?transport a mcp:Transport ; dct:identifier ?id ;
                     mcp:lifecycle ?lifecycle ; mcp:compatibilityOnly ?compatibility_only .
          ?lifecycle skos:prefLabel ?lifecycle_label .
        } ORDER BY ?id
        """,
    )
    projections = _rows(
        graph,
        """
        PREFIX mcp: <urn:gymact:mcp:>
        PREFIX dct: <http://purl.org/dc/terms/>
        SELECT ?id ?kind ?path WHERE {
          ?projection a mcp:ProjectionTarget ; dct:identifier ?id ;
                      mcp:projectionKind ?kind ; mcp:projectionPath ?path .
        } ORDER BY ?id
        """,
    )
    if len(revision) != 1:
        raise SystemExit(f"REFUSED:MCP_REVISION_CARDINALITY:{len(revision)}")
    if len(core) != 21:
        raise SystemExit(f"REFUSED:MCP_CORE_METHOD_CARDINALITY:{len(core)}")
    if len(extension) != 4:
        raise SystemExit(f"REFUSED:MCP_EXTENSION_METHOD_CARDINALITY:{len(extension)}")
    if len(projections) != 13:
        raise SystemExit(f"REFUSED:MCP_PROJECTION_CARDINALITY:{len(projections)}")

    out = [
        "//! Generated from `ggen/protocol-gym-pack/ontology.ttl`.",
        "//! Do not hand-edit this projection. Change the admitted MCP ontology and rerun ggen.",
        "",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub struct McpMethod { pub name: &'static str, pub facet: &'static str, pub lifecycle: &'static str, pub message_kind: &'static str, pub direction: &'static str, pub invocation: &'static str, pub control: &'static str, pub consequence: &'static str }",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub struct McpExtensionMethod { pub name: &'static str, pub facet: &'static str, pub extension_id: &'static str, pub lifecycle: &'static str, pub consequence: &'static str }",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub struct McpCapability { pub side: &'static str, pub key: &'static str, pub lifecycle: &'static str }",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub struct McpMetadataField { pub key: &'static str, pub required: bool, pub lifecycle: &'static str }",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub struct McpTransport { pub id: &'static str, pub lifecycle: &'static str, pub compatibility_only: bool }",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub struct McpProjectionTarget { pub id: &'static str, pub kind: &'static str, pub path: &'static str }",
        "",
        f"pub const MCP_PROTOCOL_VERSION: &str = {_rust(revision[0]['version'])};",
        "",
        "pub const MCP_CORE_METHODS: &[McpMethod] = &[",
    ]
    for row in core:
        out.append(
            "    McpMethod { "
            f"name: {_rust(row['name'])}, facet: {_rust(row['facet_id'])}, "
            f"lifecycle: {_rust(row['lifecycle_label'])}, message_kind: {_rust(row['kind_label'])}, "
            f"direction: {_rust(row['direction_label'])}, invocation: {_rust(row['invocation_label'])}, "
            f"control: {_rust(row['control_label'])}, consequence: {_rust(row['consequence_label'])} "
            "},"
        )
    out.extend(["] ;".replace(" ", ""), "", "pub const MCP_EXTENSION_METHODS: &[McpExtensionMethod] = &["])
    for row in extension:
        out.append(
            "    McpExtensionMethod { "
            f"name: {_rust(row['name'])}, facet: {_rust(row['facet_id'])}, extension_id: {_rust(row['extension_id'])}, "
            f"lifecycle: {_rust(row['lifecycle_label'])}, consequence: {_rust(row['consequence_label'])} "
            "},"
        )
    out.extend(["];", "", "pub const MCP_CAPABILITIES: &[McpCapability] = &["])
    for row in capabilities:
        out.append(f"    McpCapability {{ side: {_rust(row['side'])}, key: {_rust(row['key'])}, lifecycle: {_rust(row['lifecycle_label'])} }},")
    out.extend(["];", "", "pub const MCP_METADATA_FIELDS: &[McpMetadataField] = &["])
    for row in metadata:
        out.append(f"    McpMetadataField {{ key: {_rust(row['key'])}, required: {_bool(row['required'])}, lifecycle: {_rust(row['lifecycle_label'])} }},")
    out.extend(["];", "", "pub const MCP_TRANSPORTS: &[McpTransport] = &["])
    for row in transports:
        out.append(f"    McpTransport {{ id: {_rust(row['id'])}, lifecycle: {_rust(row['lifecycle_label'])}, compatibility_only: {_bool(row['compatibility_only'])} }},")
    out.extend(["];", "", "pub const MCP_PROJECTION_TARGETS: &[McpProjectionTarget] = &["])
    for row in projections:
        out.append(f"    McpProjectionTarget {{ id: {_rust(row['id'])}, kind: {_rust(row['kind'])}, path: {_rust(row['path'])} }},")
    out.extend([
        "];",
        "",
        "pub const MCP_CORE_METHOD_COUNT: usize = MCP_CORE_METHODS.len();",
        "pub const MCP_EXTENSION_METHOD_COUNT: usize = MCP_EXTENSION_METHODS.len();",
        "",
    ])
    return "\n".join(out)


def main() -> int:
    graph = Graph().parse(ONTOLOGY, format="turtle")
    graph = migrate_aabox(graph)
    for prefix, namespace in {
        "mcp": MCP,
        "dct": DCT,
        "prov": Namespace("http://www.w3.org/ns/prov#"),
        "skos": SKOS,
        "sosa": Namespace("http://www.w3.org/ns/sosa/"),
        "odrl": Namespace("http://www.w3.org/ns/odrl/2/"),
        "dcat": Namespace("http://www.w3.org/ns/dcat#"),
        "rdf": RDF,
    }.items():
        graph.bind(prefix, namespace, replace=True)
    ONTOLOGY.write_text(graph.serialize(format="turtle"), encoding="utf-8")
    RUST.parent.mkdir(parents=True, exist_ok=True)
    RUST.write_text(generate_rust(graph), encoding="utf-8")
    LIB.write_text(
        "pub mod authority;\npub mod capabilities;\npub mod manifest;\npub mod mcp_surface;\n"
        "pub mod protocols;\npub mod schemas;\npub mod standing;\n\n"
        "pub const DISCOVERY_IS_EXECUTION: bool = false;\n"
        "pub const ADVERTISEMENT_IS_VERIFICATION: bool = false;\n"
        "pub const MCP_VALIDITY_GRANTS_DO_AUTHORITY: bool = false;\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
