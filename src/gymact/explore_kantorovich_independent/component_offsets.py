from __future__ import annotations

from fractions import Fraction

from gymact.explore_kantorovich_duality.measure import FiniteMeasure
from gymact.explore_kantorovich_duality.metric import GroundMetric

from .refusal import IndependentVerifierRefusal
from .tight_components import TightComponents


def solve_component_offsets(components: TightComponents, source: FiniteMeasure, target: FiniteMeasure, metric: GroundMetric) -> dict[int, Fraction]:
    """Solve t_a-t_b <= c_xy-base_u[x]-base_v[y] for tight-graph components."""
    edges: list[tuple[int, int, Fraction]] = []
    for x in source.support:
        a = components.source_component[x]
        for y in target.support:
            b = components.target_component[y]
            bound = metric(x, y) - components.base_u[x] - components.base_v[y]
            if a == b:
                if bound < 0:
                    raise IndependentVerifierRefusal("INTRA_COMPONENT_DUAL_INFEASIBLE", f"{x}->{y}:{-bound}")
            else:
                edges.append((b, a, bound))
    distance = {index: Fraction(0) for index in range(components.count)}
    for _ in range(max(components.count - 1, 0)):
        changed = False
        for origin, destination, weight in edges:
            candidate = distance[origin] + weight
            if candidate < distance[destination]:
                distance[destination] = candidate
                changed = True
        if not changed:
            break
    for origin, destination, weight in edges:
        if distance[origin] + weight < distance[destination]:
            raise IndependentVerifierRefusal("DUAL_OFFSET_NEGATIVE_CYCLE", f"{origin}->{destination}")
    return distance
