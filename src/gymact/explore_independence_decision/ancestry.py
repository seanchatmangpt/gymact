from __future__ import annotations

from dataclasses import dataclass

from .errors import require


@dataclass(frozen=True)
class EvidenceRootSet:
    roots: frozenset[str]

    def __post_init__(self) -> None:
        require(bool(self.roots), "EMPTY_EVIDENCE_ROOTS")
        require(all(bool(root) for root in self.roots), "INVALID_EVIDENCE_ROOT")

    def overlap_count(self, other: "EvidenceRootSet") -> int:
        return len(self.roots & other.roots)

    def jaccard(self, other: "EvidenceRootSet") -> tuple[int, int]:
        union = self.roots | other.roots
        return len(self.roots & other.roots), len(union)

    def disjoint(self, other: "EvidenceRootSet") -> bool:
        return self.roots.isdisjoint(other.roots)
