from __future__ import annotations

from rdflib import Graph

from gymact.semantics.canonical_graph import ingest
from gymact.semantics.capability_contract import SemanticContract, executable_terms, verify_contract
from gymact.semantics.rdf_source import RDFFormat, RDFSource

TTL = b'''@prefix dct: <http://purl.org/dc/terms/> .
@prefix pplan: <http://purl.org/net/p-plan#> .
<urn:sony:media:release> a pplan:Plan ; dct:identifier "media.10.release" .
'''


def _source(content: bytes, format_: RDFFormat, name: str) -> RDFSource:
    return RDFSource(name, f"urn:test:{name}", format_, content)


def _serialized(format_: str) -> bytes:
    value = Graph().parse(data=TTL, format="turtle").serialize(format=format_)
    return value.encode() if isinstance(value, str) else value


def test_three_formats_have_one_canonical_identity() -> None:
    snapshots = (
        ingest((_source(TTL, RDFFormat.TURTLE, "ttl"),)),
        ingest((_source(_serialized("xml"), RDFFormat.RDF_XML, "xml"),)),
        ingest((_source(_serialized("json-ld"), RDFFormat.JSON_LD, "jsonld"),)),
    )
    assert len({snapshot.digest for snapshot in snapshots}) == 1
    assert {snapshot.triple_count for snapshot in snapshots} == {2}


def test_provenance_capability_and_contract() -> None:
    snapshot = ingest((_source(TTL, RDFFormat.TURTLE, "sony-media"),))
    terms = executable_terms(snapshot)
    assert len(terms) == 1
    assert terms[0].iri == "urn:sony:media:release"
    assert terms[0].identifier == "media.10.release"
    assert terms[0].source_ids == ("sony-media",)
    verify_contract(
        snapshot,
        SemanticContract(
            expected_triple_count=2,
            expected_source_count=1,
            expected_digest=snapshot.digest,
            required_iris=frozenset({"urn:sony:media:release"}),
            required_predicates=frozenset({"http://purl.org/dc/terms/identifier"}),
            executable_iris=frozenset({"urn:sony:media:release"}),
        ),
    )
