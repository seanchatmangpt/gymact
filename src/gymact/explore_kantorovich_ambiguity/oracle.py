from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from functools import reduce

from .ground import GroundMetric
from .measure import FiniteMeasure
from .refusal import Refused

@dataclass(frozen=True)
class OraclePlan:
    cost: Fraction
    shipments: tuple[tuple[str, str, Fraction], ...]

def _lcm(values: list[int]) -> int:
    return reduce(math.lcm, values, 1)

def exhaustive_transport(
    a: FiniteMeasure, b: FiniteMeasure, metric: GroundMetric, *, max_units: int = 64
) -> OraclePlan:
    den = _lcm([v.denominator for _, v in (*a.mass, *b.mass)])
    if den > max_units:
        raise Refused("ORACLE_STATE_SPACE_LIMIT", str(den))
    supply = [int(v * den) for _, v in a.mass]
    demand = [int(v * den) for _, v in b.mass]
    left, right = list(a.support), list(b.support)
    best: tuple[Fraction, tuple[tuple[str, str, Fraction], ...]] | None = None

    def rec(i: int, j: int, s: list[int], d: list[int], acc: list[tuple[str, str, int]]) -> None:
        nonlocal best
        if i == len(s):
            if any(d):
                return
            shipments = tuple((x, y, Fraction(u, den)) for x, y, u in acc if u)
            cost = sum((amt * metric.cost(x, y) for x, y, amt in shipments), Fraction())
            candidate = (cost, shipments)
            if best is None or candidate < best:
                best = candidate
            return
        if j == len(d):
            if s[i] != 0:
                return
            rec(i + 1, 0, s, d, acc)
            return
        limit = min(s[i], d[j])
        for units in range(limit + 1):
            ns, nd = s.copy(), d.copy()
            ns[i] -= units
            nd[j] -= units
            rec(i, j + 1, ns, nd, [*acc, (left[i], right[j], units)])

    rec(0, 0, supply, demand, [])
    if best is None:
        raise Refused("ORACLE_NO_FEASIBLE_TRANSPORT")
    return OraclePlan(*best)
