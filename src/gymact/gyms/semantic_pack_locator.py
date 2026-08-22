"""Deterministic, fail-closed semantic pack location admission.

This module does not fetch, mutate, or execute anything. It only admits
already-materialized pack candidates and refuses divergent ambiguity.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class SemanticPackResolution:
    """A content-bound resolution over one or more equivalent locations."""

    path: Path
    digest_sha256: str
    equivalent_paths: tuple[Path, ...]


def _digest(path: Path, required_file: str) -> str:
    return sha256((path / required_file).read_bytes()).hexdigest()


def resolve_semantic_pack(
    *,
    candidates: Iterable[Path],
    required_file: str = "ontology.ttl",
) -> SemanticPackResolution:
    """Resolve already-materialized semantic pack candidates.

    Zero materialized candidates is a typed refusal. Multiple candidates are
    admitted only when their required semantic source bytes are identical;
    otherwise ambiguity refuses instead of choosing by path precedence.
    """

    materialized = tuple(
        sorted(
            {
                Path(candidate).resolve()
                for candidate in candidates
                if (Path(candidate) / required_file).is_file()
            },
            key=str,
        )
    )
    if not materialized:
        raise ValueError("REFUSED_NO_SEMANTIC_PACK_MATERIALIZED")

    digests = {path: _digest(path, required_file) for path in materialized}
    unique_digests = frozenset(digests.values())
    if len(unique_digests) != 1:
        details = ",".join(f"{path}={digests[path]}" for path in materialized)
        raise ValueError(f"REFUSED_DIVERGENT_SEMANTIC_PACK_CANDIDATES:{details}")

    digest = next(iter(unique_digests))
    return SemanticPackResolution(
        path=materialized[0],
        digest_sha256=digest,
        equivalent_paths=materialized,
    )
