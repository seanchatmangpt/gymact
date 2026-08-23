from dataclasses import dataclass

from .errors import Refused


@dataclass(frozen=True, slots=True)
class DeferRealization:
    prior_risk: float
    posterior_risk: float
    information_gain: float
    acquisition_cost: float

    def __post_init__(self) -> None:
        if min(
            self.prior_risk,
            self.posterior_risk,
            self.information_gain,
            self.acquisition_cost,
        ) < 0:
            raise Refused("INVALID_DEFER_REALIZATION")

    @property
    def realized_risk_reduction(self) -> float:
        return self.prior_risk - self.posterior_risk

    @property
    def net_value(self) -> float:
        return self.realized_risk_reduction + self.information_gain - self.acquisition_cost
