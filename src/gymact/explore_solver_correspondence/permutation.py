from __future__ import annotations

from ..explore_kantorovich_ambiguity.measure import FiniteMeasure
from ..explore_kantorovich_ambiguity.ground import GroundMetric


def permute_measure(measure: FiniteMeasure, mapping: dict[str, str]) -> FiniteMeasure:
    return FiniteMeasure.from_mapping({mapping[k]: v for k, v in measure.mass})


def permute_metric(metric: GroundMetric, mapping: dict[str, str]) -> GroundMetric:
    points = tuple(mapping[p] for p in metric.points)
    costs = {(mapping[x], mapping[y]): metric.cost(x, y) for x in metric.points for y in metric.points}
    return GroundMetric.from_mapping(points, costs)
