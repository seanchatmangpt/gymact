from dataclasses import dataclass
from fractions import Fraction


@dataclass(slots=True)
class Cusum:
    threshold: Fraction
    slack: Fraction = Fraction()
    state: Fraction = Fraction()

    def update(self, residual: Fraction) -> bool:
        self.state = max(Fraction(), self.state + abs(residual) - self.slack)
        return self.state >= self.threshold
