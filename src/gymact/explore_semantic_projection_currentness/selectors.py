from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .representation import RepresentationCandidate
from .roundtrip import RoundTripWitness
from .subject import Refusal


class SelectorKind(StrEnum):
    MAX_FIDELITY = "MAX_FIDELITY"
    MIN_MIGRATION_COST = "MIN_MIGRATION_COST"
    MAX_REVERSIBILITY = "MAX_REVERSIBILITY"
    MINIMAX_REGRET = "MINIMAX_REGRET"


@dataclass(frozen=True, slots=True)
class Score:
    candidate: RepresentationCandidate
    fidelity_loss: Fraction
    migration_cost: int
    runtime_cost: int
    reversible: int


def score(candidate: RepresentationCandidate, witness: RoundTripWitness | None) -> Score:
    loss = (
        Fraction(0)
        if witness is None
        else (witness.forward.loss + witness.backward.loss).total
    )
    return Score(
        candidate,
        loss,
        candidate.migration_cost,
        candidate.runtime_cost,
        int(candidate.reversible),
    )


def select(kind: SelectorKind, scores: tuple[Score, ...]) -> Score:
    if not scores:
        raise Refusal("REFUSED_EMPTY_SELECTOR_FRONTIER")
    ordered = sorted(scores, key=lambda s: s.candidate.fingerprint)
    if kind is SelectorKind.MAX_FIDELITY:
        return min(ordered, key=lambda s: (s.fidelity_loss, s.runtime_cost))
    if kind is SelectorKind.MIN_MIGRATION_COST:
        return min(ordered, key=lambda s: (s.migration_cost, s.runtime_cost))
    if kind is SelectorKind.MAX_REVERSIBILITY:
        return min(ordered, key=lambda s: (-s.reversible, s.fidelity_loss, s.migration_cost))
    maxima = (
        max((s.fidelity_loss for s in ordered), default=Fraction(1)) or Fraction(1),
        max((s.migration_cost for s in ordered), default=1) or 1,
        max((s.runtime_cost for s in ordered), default=1) or 1,
    )

    def regret(s: Score) -> Fraction:
        return max(
            s.fidelity_loss / maxima[0],
            Fraction(s.migration_cost, maxima[1]),
            Fraction(s.runtime_cost, maxima[2]),
            Fraction(1 - s.reversible, 1),
        )

    return min(ordered, key=lambda s: (regret(s), s.candidate.fingerprint))
