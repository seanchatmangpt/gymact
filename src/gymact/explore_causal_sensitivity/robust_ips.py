from collections.abc import Iterable
from fractions import Fraction

from .evidence import LoggedOutcome
from .gamma import Gamma
from .manski import Interval
from .weight_interval import weight_interval


def robust_ips(rows: Iterable[LoggedOutcome], gamma: Gamma) -> Interval:
    data = tuple(rows)
    if not data:
        raise ValueError("empty log")
    lows: list[Fraction] = []
    highs: list[Fraction] = []
    for row in data:
        wi = weight_interval(row.target_propensity, row.behavior_propensity, gamma)
        candidates = (wi.lower * row.reward, wi.upper * row.reward)
        lows.append(min(candidates))
        highs.append(max(candidates))
    n = len(data)
    return Interval(sum(lows, Fraction()) / n, sum(highs, Fraction()) / n)
