from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from typing import Protocol


class TransportResult(Protocol):
    cost: Fraction
    shipments: tuple[tuple[str, str, Fraction], ...]


def _fraction_string(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


@dataclass(frozen=True)
class ResultIdentity:
    cost: Fraction
    shipments: tuple[tuple[str, str, Fraction], ...]

    @classmethod
    def from_plan(cls, plan: TransportResult) -> ResultIdentity:
        shipments = tuple(sorted(plan.shipments))
        return cls(plan.cost, shipments)

    def canonical(self) -> dict[str, object]:
        shipments = [(x, y, _fraction_string(v)) for x, y, v in self.shipments]
        return {"cost": _fraction_string(self.cost), "shipments": shipments}

    @property
    def digest(self) -> str:
        payload = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode()).hexdigest()
