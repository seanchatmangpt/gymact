from __future__ import annotations

import math

from .interval import Interval


def binary_entropy(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def acquisition_value(confidence: Interval, *, cost: float, blocker_relief: int) -> float:
    midpoint = (confidence.lower + confidence.upper) / 2.0
    epistemic = confidence.width + binary_entropy(midpoint)
    return (epistemic * (1.0 + max(0, blocker_relief))) / max(cost, 1e-9)
