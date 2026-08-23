from dataclasses import dataclass
from collections.abc import Iterable

from .errors import Refused

@dataclass(frozen=True, slots=True)
class SelectiveLoss:
    loss: float
    propensity: float

    def __post_init__(self) -> None:
        if self.loss < 0 or not 0.0 < self.propensity <= 1.0:
            raise Refused("INVALID_SELECTIVE_LOSS")


def horvitz_thompson_risk(rows: Iterable[SelectiveLoss], population_size: int) -> float:
    samples = tuple(rows)
    if population_size <= 0 or len(samples) > population_size:
        raise Refused("INVALID_POPULATION_SIZE")
    return sum(row.loss / row.propensity for row in samples) / population_size


def self_normalized_risk(rows: Iterable[SelectiveLoss]) -> float:
    samples = tuple(rows)
    if not samples:
        raise Refused("INSUFFICIENT_REALIZATION_SUPPORT")
    weights = tuple(1.0 / row.propensity for row in samples)
    denominator = sum(weights)
    return sum(weight * row.loss for weight, row in zip(weights, samples, strict=True)) / denominator
