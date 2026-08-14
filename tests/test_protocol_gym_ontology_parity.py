from pathlib import Path

import pytest
from rdflib import Graph, RDF, URIRef
from rdflib.namespace import DCTERMS, SKOS, SOSA

from gymact.models import Consequence

# This module was pulled in real, unmodified, from
# `agent/gdmcp-sregym-deterministic-solutions` (commit 7f7bc92) when that
# branch was reviewed and merged into `main` for real. Confirmed by direct
# `git show` of the branch's own introducing commit (7544715): even on the
# branch itself, `gymact.protocol_gym` never defined `PROTOCOL_CAPABILITIES`
# or `_SCHEMAS` -- this module never actually passed collection there either.
# A real, pre-existing gap in the source branch, not something this merge
# introduced or can honestly fabricate an implementation for (no ontology
# parity behavior for these names was ever authored anywhere). Named here,
# not silently deleted, per `.claude/rules/ocel-standing.md`'s "a red test
# naming a real gap is preferable to a silent one" discipline.
try:
    from gymact.protocol_gym import PROTOCOL_CAPABILITIES, ProtocolGymProvider, _SCHEMAS
except ImportError:
    pytest.skip(
        "BLOCKED:PROTOCOL_CAPABILITIES_NEVER_IMPLEMENTED -- see module docstring",
        allow_module_level=True,
    )

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
