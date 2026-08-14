from __future__ import annotations

import json
from pathlib import Path

import pytest
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, SOSA

from gymact import registry
from gymact.generated.sregym_mcp_catalog import (
    PROGRAM_SOURCE_ROWS,
    PROGRAM_STEP_ROWS,
    SREGYM_CAPABILITY_ROWS,
    SREGYM_LITE_PROBLEMS,
    SREGYM_UPSTREAM_REVISION,
)
from gymact.gyms.sregym_ontology import SREGYM_CAPABILITIES
from gymact.models import Consequence

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY = ROOT / "ggen" / "sregym-e2e-pack" / "ontology.ttl"
SR = Namespace("urn:gymact:sregym:mcp:")

EXPECTED_DO = {
    "urn:gymact:sregym:capability:run_kubectl",
    "urn:gymact:sregym:capability:submit_diagnosis",
    "urn:gymact:sregym:capability:submit_mitigation",
}
EXPECTED_ROUTES = {
    "/kubectl/sse",
    "/jaeger/sse",
    "/loki/sse",
    "/prometheus/sse",
    "/submit_mcp/sse",
    "/status",
}


def _graph() -> Graph:
    return Graph().parse(ONTOLOGY, format="turtle")


def _capability_subjects(graph: Graph) -> set[URIRef]:
    return {
        subject
        for subject in graph.subjects(RDF.type, SR.Capability)
        if (subject, RDF.type, SOSA.Procedure) in graph
    }


def test_sregym_capability_catalog_is_exactly_ontology_projection() -> None:
    graph = _graph()
    subjects = _capability_subjects(graph)
    projected = {row["iri"]: row for row in SREGYM_CAPABILITY_ROWS}

    assert len(subjects) == 14
    assert {str(subject) for subject in subjects} == set(projected)

    for subject in subjects:
        row = projected[str(subject)]
        consequence = graph.value(subject, SR.consequence)
        consequence_label = graph.value(consequence, URIRef("http://www.w3.org/2004/02/skos/core#prefLabel"))
        route_node = graph.value(subject, DCTERMS.relation)
        assert str(graph.value(subject, SR.binding)) == row["binding"]
        assert str(consequence_label) == row["consequence"]
        assert str(graph.value(route_node, SR.routePath)) == row["route"]
        tool = graph.value(subject, SR.toolName)
        assert (None if tool is None else str(tool)) == row["tool_name"]


def test_sregym_read_do_partition_matches_kernel_semantics() -> None:
    projected_do = {
        row["iri"] for row in SREGYM_CAPABILITY_ROWS if row["consequence"] == "DO"
    }
    projected_read = {
        row["iri"] for row in SREGYM_CAPABILITY_ROWS if row["consequence"] == "READ"
    }

    assert projected_do == EXPECTED_DO
    assert len(projected_do) == 3
    assert len(projected_read) == 11
    assert projected_do.isdisjoint(projected_read)
    assert len(SREGYM_CAPABILITIES) == 14
    assert sum(item.consequence is Consequence.DO for item in SREGYM_CAPABILITIES) == 3
    assert sum(item.consequence is Consequence.READ for item in SREGYM_CAPABILITIES) == 11


def test_sregym_authority_requirement_follows_consequence_partition() -> None:
    graph = _graph()
    for subject in _capability_subjects(graph):
        consequence = graph.value(subject, SR.consequence)
        required = graph.value(subject, SR.authorityRequired)
        assert required in {Literal(True), Literal(False)}
        if consequence == SR.DO:
            assert required == Literal(True)
        elif consequence == SR.READ:
            assert required == Literal(False)
        else:
            pytest.fail(f"unknown SREGym consequence classification: {consequence}")


def test_sregym_transport_route_set_is_exact() -> None:
    graph = _graph()
    routes = {
        str(route)
        for subject in _capability_subjects(graph)
        for route_node in graph.objects(subject, DCTERMS.relation)
        if (route := graph.value(route_node, SR.routePath)) is not None
    }
    assert routes == EXPECTED_ROUTES


def test_sregym_lite_corpus_and_program_set_are_exact() -> None:
    graph = _graph()
    corpus = {
        str(graph.value(subject, SR.problemId))
        for subject in graph.subjects(RDF.type, SR.CorpusSubject)
    }
    programs = {
        str(graph.value(subject, SR.problemId))
        for subject in graph.subjects(RDF.type, SR.Program)
    }

    assert corpus == set(SREGYM_LITE_PROBLEMS)
    assert len(corpus) == 21
    assert programs == {
        "wrong_dns_policy_astronomy_shop",
        "internal_traffic_policy_local_astronomy_shop",
    }
    assert programs <= corpus


def test_generated_program_sources_equal_ontology() -> None:
    graph = _graph()
    observed: set[tuple[str, str]] = set()
    for program in graph.subjects(RDF.type, SR.Program):
        problem = str(graph.value(program, SR.problemId))
        for source in graph.objects(program, SR.sourceRef):
            observed.add((problem, str(source)))
    assert observed == set(PROGRAM_SOURCE_ROWS)


def test_generated_program_steps_equal_ontology() -> None:
    graph = _graph()
    observed = []
    for step in graph.subjects(RDF.type, SR.ProgramStep):
        program = graph.value(step, SR.inProgram)
        observed.append(
            (
                str(graph.value(program, SR.problemId)),
                int(graph.value(step, SR.stepOrder)),
                str(graph.value(step, SR.stepCapability)),
                json.loads(str(graph.value(step, SR.payloadTemplateJson))),
                str(graph.value(step, SR.purpose)),
                str(graph.value(step, SR.sourceRef)),
            )
        )
    observed.sort(key=lambda item: (item[0], item[1]))
    expected = sorted(PROGRAM_STEP_ROWS, key=lambda item: (item[0], item[1]))
    assert observed == expected


def test_registered_sregym_is_ontology_adapter_not_physics_metadata() -> None:
    provider_type, capabilities = registry._BUILTINS["sregym"]
    assert provider_type.__name__ == "SregymOntologyProvider"
    assert provider_type.__module__ == "gymact.gyms.sregym_ontology"
    assert capabilities == SREGYM_CAPABILITIES


def test_sregym_exact_revision_is_single_across_projection_and_e2e_contract() -> None:
    graph = _graph()
    contract = URIRef("urn:gymact:sregym:e2e:contract")
    assert str(graph.value(contract, DCTERMS.hasVersion)) == SREGYM_UPSTREAM_REVISION
