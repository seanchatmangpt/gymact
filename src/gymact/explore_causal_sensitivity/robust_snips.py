from collections.abc import Iterable
from fractions import Fraction

from .evidence import LoggedOutcome
from .gamma import Gamma
from .manski import Interval
from .weight_interval import weight_interval


def robust_snips(rows: Iterable[LoggedOutcome], gamma: Gamma) -> Interval:
    data = tuple(rows)
    if not data:
        raise ValueError("empty log")
    intervals = [weight_interval(r.target_propensity, r.behavior_propensity, gamma) for r in data]
    low_den = sum((w.lower for w in intervals), Fraction())
    high_den = sum((w.upper for w in intervals), Fraction())
    if low_den <= 0 or high_den <= 0:
        raise ValueError("zero target mass")
    low_num = sum(
        (
            min(w.lower * r.reward, w.upper * r.reward)
            for r, w in zip(data, intervals, strict=True)
        ),
        Fraction(),
    )
    high_num = sum(
        (
            max(w.lower * r.reward, w.upper * r.reward)
            for r, w in zip(data, intervals, strict=True)
        ),
        Fraction(),
    )
    return Interval(low_num / high_den, high_num / low_den)
