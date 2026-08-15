from __future__ import annotations

from gymact.semantics.canonical_graph import ingest_paths

TTL = b'''@prefix dct: <http://purl.org/dc/terms/> .
<urn:enterprise:artifact> dct:identifier "artifact.1" .
'''


def test_ingestion_is_deterministic_and_leaves_source_tree_unchanged(tmp_path) -> None:
    path = tmp_path / "ontology.ttl"
    path.write_bytes(TTL)
    before = path.read_bytes()
    before_entries = tuple(tmp_path.iterdir())

    first = ingest_paths((path,))
    second = ingest_paths((path,))

    assert first.digest == second.digest
    assert first.canonical_ntriples == second.canonical_ntriples
    assert path.read_bytes() == before
    assert tuple(tmp_path.iterdir()) == before_entries
