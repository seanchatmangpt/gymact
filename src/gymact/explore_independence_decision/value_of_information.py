from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .errors import require


@dataclass(frozen=True)
class InformationOption:
    name: str
    expected_risk_reduction: Fraction
    cost: Fraction

    def __post_init__(self) -> None:
        require(bool(self.name), "MISSING_OPTION_NAME")
        require(self.expected_risk_reduction >= 0, "NEGATIVE_RISK_REDUCTION")
        require(self.cost >= 0, "NEGATIVE_INFORMATION_COST")

    @property
    def net_value(self) -> Fraction:
        return self.expected_risk_reduction - self.cost


def best_option(options: tuple[InformationOption, ...]) -> InformationOption | None:
    viable = [option for option in options if option.net_value > 0]
    if not viable:
        return None
    return max(
        viable,
        key=lambda option: (option.net_value, option.expected_risk_reduction, option.name),
    )
