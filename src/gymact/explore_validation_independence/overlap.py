from dataclasses import dataclass
from fractions import Fraction
from .ancestry import EvidenceGraph

@dataclass(frozen=True)
class Overlap:
    shared: int
    union: int

    @property
    def ratio(self) -> Fraction:
        return Fraction(self.shared, self.union) if self.union else Fraction(0)

def ancestry_overlap(graph: EvidenceGraph, left: str, right: str) -> Overlap:
    a = set(graph.ancestors(left)) | {left}
    b = set(graph.ancestors(right)) | {right}
    return Overlap(len(a & b), len(a | b))
