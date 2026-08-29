from __future__ import annotations

from dataclasses import dataclass
from .result_identity import ResultIdentity
from .subject import SolverSubject
from ..explore_kantorovich_ambiguity.oracle import exhaustive_transport

@dataclass(frozen=True)
class OracleObservation:
    subject: SolverSubject
    engine: str
    result: ResultIdentity


def run_oracle(subject: SolverSubject, a: object, b: object, metric: object, *, max_units: int = 64) -> OracleObservation:
    plan = exhaustive_transport(a, b, metric, max_units=max_units)
    return OracleObservation(subject, "gymact.kantorovich.exhaustive/v1", ResultIdentity.from_plan(plan))
