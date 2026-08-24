from __future__ import annotations

from fractions import Fraction

from ..explore_kantorovich_ambiguity.ground import GroundMetric
from ..explore_kantorovich_ambiguity.measure import FiniteMeasure


def line_metric(points: tuple[str, ...]) -> GroundMetric:
    costs: dict[tuple[str, str], Fraction] = {}
    for i, x in enumerate(points):
        for j, y in enumerate(points):
            costs[(x, y)] = Fraction(abs(i - j))
    return GroundMetric.from_mapping(points, costs)


def corpus(max_support: int = 6):
    for n in range(2, max_support + 1):
        points = tuple(f"s{i}" for i in range(n))
        a = FiniteMeasure.from_mapping({p: i + 1 for i, p in enumerate(points)})
        b = FiniteMeasure.from_mapping({p: n - i for i, p in enumerate(points)})
        yield a, b, line_metric(points)
