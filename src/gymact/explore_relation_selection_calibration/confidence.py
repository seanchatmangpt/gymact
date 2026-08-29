from __future__ import annotations

from math import sqrt


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("invalid binomial sample")
    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denom
    radius = z * sqrt((p * (1.0 - p) / total) + z2 / (4.0 * total * total)) / denom
    return max(0.0, center - radius), min(1.0, center + radius)


def error_upper(errors: int, total: int) -> float:
    return wilson_interval(errors, total)[1]
