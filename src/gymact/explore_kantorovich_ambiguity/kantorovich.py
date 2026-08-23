from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .flow import MinCostFlow
from .ground import GroundMetric
from .measure import FiniteMeasure, common_support
from .refusal import Refused

@dataclass(frozen=True)
class TransportPlan:
    cost: Fraction
    shipments: tuple[tuple[str, str, Fraction], ...]

def wasserstein1(a: FiniteMeasure, b: FiniteMeasure, metric: GroundMetric) -> TransportPlan:
    support = common_support(a, b)
    missing = set(support) - set(metric.points)
    if missing:
        raise Refused("GROUND_METRIC_SUPPORT_GAP", ",".join(sorted(missing)))
    left = list(a.support)
    right = list(b.support)
    n = 2 + len(left) + len(right)
    source, sink = n - 2, n - 1
    flow = MinCostFlow(n)
    for i, point in enumerate(left):
        flow.add_edge(source, i, a.probability(point), Fraction())
    offset = len(left)
    for j, point in enumerate(right):
        flow.add_edge(offset + j, sink, b.probability(point), Fraction())
    for i, x in enumerate(left):
        for j, y in enumerate(right):
            flow.add_edge(i, offset + j, Fraction(1), metric.cost(x, y))
    result = flow.solve(source, sink, Fraction(1))
    shipments = []
    for u, v, amount in result.edge_flows:
        if u < len(left) and offset <= v < offset + len(right):
            shipments.append((left[u], right[v - offset], amount))
    return TransportPlan(result.cost, tuple(sorted(shipments)))
