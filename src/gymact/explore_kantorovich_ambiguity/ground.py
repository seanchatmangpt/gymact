from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from .measure import q
from .refusal import Refused

@dataclass(frozen=True)
class GroundMetric:
    points: tuple[str, ...]
    costs: tuple[tuple[str, str, Fraction], ...]

    @classmethod
    def from_mapping(
        cls, points: tuple[str, ...], costs: Mapping[tuple[str, str], int | str | Fraction]
    ) -> "GroundMetric":
        pts = tuple(dict.fromkeys(points))
        if not pts:
            raise Refused("EMPTY_GROUND_SPACE")
        normalized: dict[tuple[str, str], Fraction] = {}
        for a in pts:
            for b in pts:
                if (a, b) not in costs:
                    raise Refused("MISSING_GROUND_COST", f"{a}->{b}")
                value = q(costs[a, b])
                if value < 0:
                    raise Refused("NEGATIVE_GROUND_COST", f"{a}->{b}")
                normalized[a, b] = value
        for a in pts:
            if normalized[a, a] != 0:
                raise Refused("NONZERO_GROUND_DIAGONAL", a)
            for b in pts:
                if normalized[a, b] != normalized[b, a]:
                    raise Refused("ASYMMETRIC_GROUND_COST", f"{a},{b}")
                for c in pts:
                    if normalized[a, c] > normalized[a, b] + normalized[b, c]:
                        raise Refused("TRIANGLE_INEQUALITY", f"{a},{b},{c}")
        return cls(pts, tuple((a, b, normalized[a, b]) for a in pts for b in pts))

    def cost(self, a: str, b: str) -> Fraction:
        try:
            return {(x, y): c for x, y, c in self.costs}[a, b]
        except KeyError as exc:
            raise Refused("GROUND_POINT_OUTSIDE_METRIC", f"{a},{b}") from exc
