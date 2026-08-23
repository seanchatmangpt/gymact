from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction

from gymact.explore_kantorovich_duality.metric import GroundMetric
from gymact.explore_kantorovich_duality.plan import TransportPlan

from .refusal import IndependentVerifierRefusal


@dataclass(frozen=True)
class TightComponents:
    source_component: dict[str, int]
    target_component: dict[str, int]
    base_u: dict[str, Fraction]
    base_v: dict[str, Fraction]
    count: int


def derive_tight_components(plan: TransportPlan, source_support: set[str], target_support: set[str], metric: GroundMetric) -> TightComponents:
    source_neighbors = {x: [] for x in source_support}
    target_neighbors = {y: [] for y in target_support}
    for (x, y), amount in plan.flow.items():
        if amount > 0:
            source_neighbors[x].append(y)
            target_neighbors[y].append(x)
    sc: dict[str, int] = {}
    tc: dict[str, int] = {}
    u: dict[str, Fraction] = {}
    v: dict[str, Fraction] = {}
    component = 0
    pending_sources = sorted(source_support)
    for root in pending_sources:
        if root in sc:
            continue
        u[root] = Fraction(0)
        sc[root] = component
        queue: deque[tuple[str, str]] = deque([("s", root)])
        while queue:
            side, node = queue.popleft()
            if side == "s":
                for y in source_neighbors[node]:
                    implied = metric(node, y) - u[node]
                    if y in v and v[y] != implied:
                        raise IndependentVerifierRefusal("INCONSISTENT_TIGHT_CYCLE", f"target:{y}")
                    if y not in v:
                        v[y] = implied
                        tc[y] = component
                        queue.append(("t", y))
            else:
                for x in target_neighbors[node]:
                    implied = metric(x, node) - v[node]
                    if x in u and u[x] != implied:
                        raise IndependentVerifierRefusal("INCONSISTENT_TIGHT_CYCLE", f"source:{x}")
                    if x not in u:
                        u[x] = implied
                        sc[x] = component
                        queue.append(("s", x))
        component += 1
    for y in sorted(target_support):
        if y not in tc:
            tc[y] = component
            v[y] = Fraction(0)
            component += 1
    return TightComponents(sc, tc, u, v, component)
