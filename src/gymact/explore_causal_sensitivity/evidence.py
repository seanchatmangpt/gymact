from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, order=True)
class LoggedOutcome:
    context: str
    action: str
    reward: Fraction
    behavior_propensity: Fraction
    target_propensity: Fraction

    def validate(self, lower: Fraction, upper: Fraction) -> None:
        if lower > upper:
            raise ValueError("invalid outcome bounds")
        if not lower <= self.reward <= upper:
            raise ValueError("reward outside declared bounds")
        if not 0 < self.behavior_propensity <= 1:
            raise ValueError("behavior propensity must be in (0,1]")
        if not 0 <= self.target_propensity <= 1:
            raise ValueError("target propensity must be in [0,1]")
