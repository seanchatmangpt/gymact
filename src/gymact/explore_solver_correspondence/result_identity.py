from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json

@dataclass(frozen=True)
class ResultIdentity:
    cost: Fraction
    shipments: tuple[tuple[str, str, Fraction], ...]

    @classmethod
    def from_plan(cls, plan: object) -> "ResultIdentity":
        shipments = tuple(sorted(getattr(plan, "shipments")))
        return cls(getattr(plan, "cost"), shipments)

    def canonical(self) -> dict[str, object]:
        return {"cost": f"{self.cost.numerator}/{self.cost.denominator}", "shipments": [(x, y, f"{v.numerator}/{v.denominator}") for x, y, v in self.shipments]}

    @property
    def digest(self) -> str:
        raw = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":")).encode()
        return sha256(raw).hexdigest()
