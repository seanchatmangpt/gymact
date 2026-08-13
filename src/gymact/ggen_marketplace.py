"""Deterministic review of the canonical ggen marketplace for GymAct hub relevance.

This module is SELECT/CONSTRUCT only. It reads pack manifests and ranks them; it never
executes ggen, imports pack code, follows network references, or grants DO authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")

_RELEVANCE_DIMENSIONS: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("federation", 20, ("federat", "semantic registry", "registry")),
    ("capability", 12, ("capabilit", "provider", "ontology", "rdf", "semantic")),
    ("authority", 12, ("authority", "policy", "admission", "refusal", "gate")),
    ("evidence", 10, ("receipt", "replay", "standing", "evidence", "provenance")),
    ("autonomic", 8, ("autonomic", "automatic", "unattended", "self-heal", "operations")),
    ("combinatorial", 8, ("combinatorial", "maximalism", "planner", "planning", "broker")),
    ("interop", 6, ("mcp", "protocol", "wit", "wasm", "api", "interface")),
    ("global-runtime", 4, ("cloud", "multi-cloud", "distributed", "event", "workflow")),
)


@dataclass(frozen=True, slots=True)
class MarketplacePack:
    name: str
    version: str
    description: str
    path: Path


@dataclass(frozen=True, slots=True)
class PackRelevance:
    pack: MarketplacePack
    score: int
    dimensions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarketplaceReview:
    root: Path
    examined: int
    ranked: tuple[PackRelevance, ...]

    def top(self, limit: int = 10) -> tuple[PackRelevance, ...]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        return self.ranked[:limit]


def _load_manifest(path: Path) -> MarketplacePack:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"INVALID_PACK_MANIFEST:{path}:{type(exc).__name__}") from exc
    pack = data.get("pack")
    if not isinstance(pack, dict):
        raise ValueError(f"INVALID_PACK_MANIFEST:{path}:MISSING_PACK_TABLE")
    name = pack.get("name")
    version = pack.get("version")
    description = pack.get("description")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"INVALID_PACK_MANIFEST:{path}:MISSING_NAME")
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise ValueError(f"INVALID_PACK_MANIFEST:{path}:INVALID_SEMVER")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"INVALID_PACK_MANIFEST:{path}:MISSING_DESCRIPTION")
    if path.parent.name != name:
        raise ValueError(f"INVALID_PACK_MANIFEST:{path}:DIRECTORY_NAME_MISMATCH")
    return MarketplacePack(name=name, version=version, description=description, path=path.parent)


def _score(pack: MarketplacePack) -> PackRelevance:
    haystack = f"{pack.name} {pack.description}".casefold()
    dimensions: list[str] = []
    score = 0
    for dimension, weight, needles in _RELEVANCE_DIMENSIONS:
        if any(needle in haystack for needle in needles):
            dimensions.append(dimension)
            score += weight
    return PackRelevance(pack=pack, score=score, dimensions=tuple(dimensions))


def review_marketplace(root: str | Path) -> MarketplaceReview:
    """Review every admitted ``packs/*/pack.toml`` under a local marketplace checkout.

    Malformed manifests fail closed instead of disappearing from the review. Pack templates,
    gates, and generated code are not executed: catalog review is not pack execution.
    """

    root = Path(root).expanduser().resolve()
    packs_root = root / "packs"
    if not packs_root.is_dir():
        raise ValueError(f"MARKETPLACE_PACKS_NOT_FOUND:{packs_root}")
    manifests = tuple(sorted(packs_root.glob("*/pack.toml")))
    if not manifests:
        raise ValueError(f"MARKETPLACE_EMPTY:{packs_root}")
    packs = tuple(_load_manifest(path) for path in manifests)
    ranked = tuple(
        sorted(
            (_score(pack) for pack in packs),
            key=lambda item: (-item.score, item.pack.name),
        )
    )
    return MarketplaceReview(root=root, examined=len(packs), ranked=ranked)
