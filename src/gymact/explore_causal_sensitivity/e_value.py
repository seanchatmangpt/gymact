from fractions import Fraction

from .manski import Interval


def evidence_value(interval: Interval, outcome_span: Fraction) -> Fraction:
    if outcome_span <= 0:
        raise ValueError("outcome span must be positive")
    width = interval.width()
    if width < 0:
        raise ValueError("invalid interval")
    score = Fraction(1) - width / outcome_span
    return max(Fraction(0), min(Fraction(1), score))
