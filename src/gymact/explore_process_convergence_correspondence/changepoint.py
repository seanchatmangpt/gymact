from dataclasses import dataclass
from fractions import Fraction
from .errors import Refused

@dataclass(frozen=True)
class ChangePoint:
    index: int
    score: Fraction

def cusum(values: tuple[Fraction, ...], threshold: Fraction) -> ChangePoint | None:
    if threshold <= 0:
        raise Refused("REFUSED_INVALID_THRESHOLD")
    if len(values) < 2:
        return None
    baseline = values[0]
    accumulated = Fraction()
    for index, value in enumerate(values[1:], 1):
        accumulated += value - baseline
        if abs(accumulated) >= threshold:
            return ChangePoint(index, accumulated)
    return None
