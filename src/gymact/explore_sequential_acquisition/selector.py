from dataclasses import dataclass
from fractions import Fraction
from .budget import Budget
from .sensor import SensorCapability
from .strategy import CandidateScore, Strategy, score


@dataclass(frozen=True)
class Selection:
    sensor: SensorCapability
    score: Fraction


def select(candidates: tuple[SensorCapability, ...], scores: dict[str, CandidateScore], budget: Budget, strategy: Strategy) -> Selection:
    lawful = [c for c in candidates if budget.admits(cost=c.cost, latency_ms=c.latency_ms) and c.digest in scores]
    if not lawful:
        raise ValueError("REFUSED_NO_LAWFUL_ACQUISITION")
    ranked = sorted(lawful, key=lambda c: (score(scores[c.digest], strategy), c.digest), reverse=True)
    winner = ranked[0]
    return Selection(winner, score(scores[winner.digest], strategy))
