from dataclasses import dataclass
from fractions import Fraction

from .clusters import EvidenceCluster


@dataclass(frozen=True, slots=True)
class ConsensusMetrics:
    cluster_count: int
    evidence_count: int
    effective_diversity: Fraction
    correlated_fraction: Fraction


def measure(clusters: tuple[EvidenceCluster, ...]) -> ConsensusMetrics:
    sizes = [len(c.members) for c in clusters]
    total = sum(sizes)
    if total == 0:
        return ConsensusMetrics(0, 0, Fraction(0), Fraction(0))
    denom = sum(size * size for size in sizes)
    diversity = Fraction(total * total, denom)
    correlated = Fraction(sum(size for size in sizes if size > 1), total)
    return ConsensusMetrics(len(clusters), total, diversity, correlated)
