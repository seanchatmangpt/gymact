from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ggen" / "protocol-gym-pack" / "ontology.ttl"
SHAPES = ROOT / "ggen" / "protocol-gym-pack" / "gates" / "mcp-surface.shacl.ttl"

MCP = Namespace("urn:gymact:mcp:")
ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
PROV = Namespace("http://www.w3.org/ns/prov#")

EXPECTED_2026_07_28_CORE_METHODS = {
    "completion/complete",
    "elicitation/create",
    "notifications/cancelled",
    "notifications/message",
    "notifications/progress",
    "notifications/prompts/list_changed",
    "notifications/resources/list_changed",
    "notifications/resources/updated",
    "notifications/subscriptions/acknowledged",
    "notifications/tools/list_changed",
    "prompts/get",
    "prompts/list",
    "resources/list",
    "resources/read",
    "resources/templates/list",
    "roots/list",
    "sampling/createMessage",
    "server/discover",
    "subscriptions/listen",
    "tools/call",
    "tools/list",
}

EXPECTED_TASK_EXTENSION_METHODS = {
    "notifications/tasks",
    "tasks/cancel",
    "tasks/get",
    "tasks/update",
}

EXPECTED_EMBEDDED_MRTR_KINDS = {
    "elicitation/create",
    "roots/list",
    "sampling/createMessage",
}


def _graph() -> Graph:
    return Graph().parse(ONTOLOGY, format="turtle")


def _method_names(graph: Graph, subjects: set) -> set[str]:
    return {str(graph.value(subject, MCP.methodName)) for subject in subjects}


def test_protocol_ontology_conforms_to_its_admission_shapes() -> None:
    graph = _graph()
    shapes = Graph().parse(SHAPES, format="turtle")

    conforms, _, report = validate(
        data_graph=graph,
        shacl_graph=shapes,
        inference="none",
        advanced=True,
    )

    assert conforms, report


def test_modern_core_method_closure_matches_official_2026_07_28_surface() -> None:
    graph = _graph()
    revision = MCP["revision-2026-07-28"]
    current_methods = {
        subject
        for subject in graph.subjects(MCP.inRevision, revision)
        if (subject, RDF.type, MCP.Method) in graph
    }

    assert _method_names(graph, current_methods) == EXPECTED_2026_07_28_CORE_METHODS
    assert len(current_methods) == 21
    assert all(
        graph.value(subject, MCP.lifecycle) != MCP.Removed for subject in current_methods
    )


def test_modern_mrtr_embeds_server_intent_instead_of_server_to_client_rpc() -> None:
    graph = _graph()
    embedded = {
        subject
        for subject in graph.subjects(MCP.invocationMode, MCP.EmbeddedMRTR)
        if (subject, RDF.type, MCP.Method) in graph
    }

    assert _method_names(graph, embedded) == EXPECTED_EMBEDDED_MRTR_KINDS
    assert all(
        graph.value(subject, MCP.messageKind) == MCP.EmbeddedInputRequest
        for subject in embedded
    )
    assert all(
        graph.value(subject, MCP.direction) == MCP.ServerIntentClientResponse
        for subject in embedded
    )


def test_removed_legacy_methods_are_compatibility_only_and_outside_modern() -> None:
    graph = _graph()
    revision = MCP["revision-2026-07-28"]
    removed = {
        subject
        for subject in graph.subjects(MCP.lifecycle, MCP.Removed)
        if (subject, RDF.type, MCP.Method) in graph
    }

    assert {
        "initialize",
        "notifications/initialized",
        "ping",
        "logging/setLevel",
        "resources/subscribe",
        "resources/unsubscribe",
        "tasks/list",
        "tasks/result",
    } <= _method_names(graph, removed)
    for subject in removed:
        assert graph.value(subject, MCP.compatibilityOnly) == Literal(True)
        assert (subject, MCP.inRevision, revision) not in graph


def test_tasks_are_a_negotiated_extension_not_a_core_method_leak() -> None:
    graph = _graph()
    tasks = MCP["extension-tasks"]
    extension_methods = {
        subject
        for subject in graph.subjects(MCP.extension, tasks)
        if (subject, RDF.type, MCP.Method) in graph
    }

    assert _method_names(graph, extension_methods) == EXPECTED_TASK_EXTENSION_METHODS
    assert str(graph.value(tasks, MCP.extensionId)) == "io.modelcontextprotocol/tasks"
    assert all(
        graph.value(subject, MCP.lifecycle) == MCP.ExtensionLifecycle
        for subject in extension_methods
    )
    assert all(graph.value(subject, MCP.inRevision) is None for subject in extension_methods)


def test_required_per_request_meta_is_explicit_and_revision_bound() -> None:
    graph = _graph()
    required_fields = {
        str(graph.value(subject, MCP.metaKey))
        for subject in graph.subjects(MCP.required, Literal(True))
        if (subject, RDF.type, MCP.MetadataField) in graph
    }

    assert required_fields == {
        "io.modelcontextprotocol/protocolVersion",
        "io.modelcontextprotocol/clientCapabilities",
    }


def test_tools_call_is_conditional_effect_not_ambient_do_authority() -> None:
    graph = _graph()
    method = MCP["method-tools-call"]

    assert graph.value(method, MCP.consequence) == MCP.ConditionalEffect
    assert graph.value(method, MCP.controlMode) == MCP.ModelControlled
    assert (MCP["gymact-brce-do-policy"], RDF.type, ODRL.Policy) in graph


def test_transport_and_header_models_preserve_body_as_semantic_source() -> None:
    graph = _graph()

    assert graph.value(MCP["transport-stdio"], MCP.lifecycle) == MCP.Active
    assert graph.value(MCP["transport-streamable-http"], MCP.lifecycle) == MCP.Active
    assert (
        graph.value(MCP["transport-legacy-http-sse"], MCP.compatibilityOnly)
        == Literal(True)
    )

    protocol_header = MCP["header-protocol-version"]
    parameter_header = MCP["header-param-mirror"]
    assert graph.value(protocol_header, MCP.bodySource) == MCP["meta-protocol-version"]
    assert graph.value(parameter_header, MCP.bodySource) == MCP["json-schema-2020-12"]
    assert str(graph.value(parameter_header, MCP.mismatchRefusal)) == "HEADER_MISMATCH"


def test_projection_catalog_is_single_source_for_all_mcp_facets() -> None:
    graph = _graph()
    projections = set(graph.subjects(RDF.type, MCP.ProjectionTarget))
    paths = [str(graph.value(subject, MCP.projectionPath)) for subject in projections]

    assert len(projections) == 13
    assert len(paths) == len(set(paths))
    assert {
        "generated/mcp/server-capabilities.json",
        "generated/mcp/client-capabilities.json",
        "generated/mcp/method-router",
        "generated/mcp/schema",
        "generated/mcp/header-policy",
        "generated/mcp/brce-map",
        "generated/mcp/subscriptions",
        "generated/mcp/mrtr",
        "generated/mcp/extensions",
        "generated/mcp/conformance",
        "rust/protocol_gym/src/mcp_surface.rs",
        "rust/protocol_gym/wit/mcp-surface.wit",
        "rust/protocol_gym/docs/mcp-surface.md",
    } == set(paths)


def test_exact_upstream_revision_and_schema_dialect_are_receipted() -> None:
    graph = _graph()
    revision = MCP["revision-2026-07-28"]

    assert str(graph.value(revision, MCP.protocolVersion)) == "2026-07-28"
    assert str(graph.value(revision, PROV.value)) == (
        "schema.ts@9b55feeb412bc3ae877f2eac10b5c01ba29a2eed"
    )
    assert str(graph.value(MCP["json-schema-2020-12"], MCP.schemaDialect)) == (
        "https://json-schema.org/draft/2020-12/schema"
    )
