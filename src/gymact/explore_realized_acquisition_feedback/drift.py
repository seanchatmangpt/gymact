from dataclasses import dataclass
from fractions import Fraction

@dataclass
class CusumDrift:
    threshold: Fraction
    positive: Fraction = Fraction(0)
    negative: Fraction = Fraction(0)

    def update(self, error: Fraction) -> bool:
        self.positive = max(Fraction(0), self.positive + error)
        self.negative = min(Fraction(0), self.negative + error)
        return self.positive >= self.threshold or -self.negative >= self.threshold
