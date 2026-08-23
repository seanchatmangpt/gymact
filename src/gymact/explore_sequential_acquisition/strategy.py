from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction


class Strategy(StrEnum):
    MAX_INFORMATION = "MAX_INFORMATION"
    INFORMATION_PER_COST = "INFORMATION_PER_COST"
    UCB_DISCOVERY = "UCB_DISCOVERY"
    MINIMAX_REGRET = "MINIMAX_REGRET"
    DIVERSITY_FIRST = "DIVERSITY_FIRST"


@dataclass(frozen=True)
class CandidateScore:
    sensor: str
    information: Fraction
    cost: Fraction
    uncertainty: Fraction
    regret: Fraction
    diversity: Fraction


def score(candidate: CandidateScore, strategy: Strategy) -> Fraction:
    if strategy is Strategy.MAX_INFORMATION:
        return candidate.information
    if strategy is Strategy.INFORMATION_PER_COST:
        return candidate.information / candidate.cost if candidate.cost else candidate.information
    if strategy is Strategy.UCB_DISCOVERY:
        return candidate.information + candidate.uncertainty
    if strategy is Strategy.MINIMAX_REGRET:
        return -candidate.regret
    return candidate.diversity
