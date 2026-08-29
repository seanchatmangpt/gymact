from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True)
class Witness:
    source: str
    target: str
    preserved: frozenset[str]
    lost: frozenset[str]
    confidence: Fraction
    def is_lossless(self) -> bool:
        return not self.lost and self.confidence == 1
    def preserves(self, obligations: frozenset[str]) -> bool:
        return obligations <= self.preserved and not (obligations & self.lost)
