from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class BeliefState:
    hypotheses: tuple[str, ...]
    probabilities: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        if not self.hypotheses or len(self.hypotheses) != len(self.probabilities):
            raise ValueError("REFUSED_INVALID_BELIEF")
        if any(p < 0 or p > 1 for p in self.probabilities) or sum(self.probabilities) != 1:
            raise ValueError("REFUSED_NON_NORMALIZED_BELIEF")
        if len(set(self.hypotheses)) != len(self.hypotheses):
            raise ValueError("REFUSED_DUPLICATE_HYPOTHESIS")

    def probability(self, hypothesis: str) -> Fraction:
        return self.probabilities[self.hypotheses.index(hypothesis)]
