from __future__ import annotations

from dataclasses import dataclass

from .evidence import Evidence, Outcome
from .supersession import Supersession


@dataclass(frozen=True)
class Frontier:
    current: tuple[Evidence, ...]
    historical: tuple[Evidence, ...]

    @property
    def standing(self) -> str:
        outcomes = {row.outcome for row in self.current}
        if Outcome.FAIL in outcomes:
            return "BUILD_BROKEN"
        if Outcome.PENDING in outcomes or Outcome.UNKNOWN in outcomes:
            return "UNKNOWN"
        if outcomes and outcomes <= {Outcome.UNSUPPORTED}:
            return "UNSUPPORTED"
        if outcomes and outcomes <= {Outcome.PASS, Outcome.UNSUPPORTED}:
            return "PARTIAL_ALIVE"
        return "UNKNOWN"


def resolve_frontier(evidence: tuple[Evidence, ...], edges: tuple[Supersession, ...]) -> Frontier:
    superseded = {edge.older for edge in edges}
    current = tuple(row for row in evidence if row not in superseded)
    historical = tuple(row for row in evidence if row in superseded)
    return Frontier(current=current, historical=historical)
