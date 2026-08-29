from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Candidate:
    name: str
    width: Fraction
    evidence_value: Fraction
    gamma_breakdown: Fraction


def frontier(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    kept: list[Candidate] = []
    for c in candidates:
        dominated = any(
            other != c
            and other.width <= c.width
            and other.evidence_value >= c.evidence_value
            and other.gamma_breakdown >= c.gamma_breakdown
            and (
                other.width < c.width
                or other.evidence_value > c.evidence_value
                or other.gamma_breakdown > c.gamma_breakdown
            )
            for other in candidates
        )
        if not dominated:
            kept.append(c)
    return tuple(sorted(kept, key=lambda item: item.name))
