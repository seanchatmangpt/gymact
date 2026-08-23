from collections.abc import Iterable

from .errors import Refused


def brier_score(predictions: Iterable[tuple[float, bool]]) -> float:
    rows = tuple(predictions)
    if not rows:
        raise Refused("INSUFFICIENT_REALIZATION_SUPPORT")
    total = 0.0
    for probability, observed in rows:
        if not 0.0 <= probability <= 1.0:
            raise Refused("INVALID_PROBABILITY")
        total += (probability - float(observed)) ** 2
    return total / len(rows)
