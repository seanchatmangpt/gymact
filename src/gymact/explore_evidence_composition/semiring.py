from __future__ import annotations

from dataclasses import dataclass

from .interval import Interval


@dataclass(frozen=True, slots=True)
class EvidenceWeight:
    confidence: Interval
    cost: float
    blockers: frozenset[str] = frozenset()

    def series(self, other: EvidenceWeight, *, independent: bool = False) -> EvidenceWeight:
        confidence = (
            self.confidence.independent_product(other.confidence)
            if independent
            else self.confidence.meet(other.confidence)
        )
        return EvidenceWeight(confidence, self.cost + other.cost, self.blockers | other.blockers)

    def parallel(self, other: EvidenceWeight) -> EvidenceWeight:
        """Keep the stronger lower bound and cheaper route without summing dependent proof."""
        return EvidenceWeight(
            Interval(
                max(self.confidence.lower, other.confidence.lower),
                max(self.confidence.upper, other.confidence.upper),
            ),
            min(self.cost, other.cost),
            self.blockers & other.blockers,
        )
