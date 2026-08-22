from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from gymact.gyms.semantic_pack_locator import resolve_semantic_pack


def _pack(root: Path, name: str, ttl: bytes) -> Path:
    path = root / name
    path.mkdir()
    (path / "ontology.ttl").write_bytes(ttl)
    return path


def test_single_materialized_candidate_is_content_bound(tmp_path: Path) -> None:
    pack = _pack(tmp_path, "one", b"@prefix ex: <urn:example:> .\n")

    resolved = resolve_semantic_pack(candidates=[pack])

    assert resolved.path == pack.resolve()
    assert resolved.equivalent_paths == (pack.resolve(),)
    assert resolved.digest_sha256 == sha256((pack / "ontology.ttl").read_bytes()).hexdigest()


def test_equivalent_candidates_preserve_multiple_lawful_locations(tmp_path: Path) -> None:
    ttl = b"@prefix ex: <urn:example:> .\n"
    first = _pack(tmp_path, "a", ttl)
    second = _pack(tmp_path, "b", ttl)

    resolved = resolve_semantic_pack(candidates=[second, first])

    assert resolved.path == first.resolve()
    assert resolved.equivalent_paths == (first.resolve(), second.resolve())


def test_divergent_candidates_refuse_instead_of_using_path_precedence(tmp_path: Path) -> None:
    first = _pack(tmp_path, "a", b"<urn:a> <urn:p> <urn:o> .\n")
    second = _pack(tmp_path, "b", b"<urn:b> <urn:p> <urn:o> .\n")

    with pytest.raises(ValueError, match="REFUSED_DIVERGENT_SEMANTIC_PACK_CANDIDATES"):
        resolve_semantic_pack(candidates=[first, second])


def test_missing_candidates_refuse_without_inventing_semantics(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="REFUSED_NO_SEMANTIC_PACK_MATERIALIZED"):
        resolve_semantic_pack(candidates=[tmp_path / "missing"])
