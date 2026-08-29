from __future__ import annotations

from dataclasses import dataclass
from .result_identity import ResultIdentity
from .subject import SolverSubject
from ..explore_kantorovich_ambiguity.kantorovich import wasserstein1

@dataclass(frozen=True)
class SolverObservation:
    subject: SolverSubject
    engine: str
    result: ResultIdentity


def run_primal(subject: SolverSubject, a: object, b: object, metric: object) -> SolverObservation:
    plan = wasserstein1(a, b, metric)
    return SolverObservation(subject, "gymact.kantorovich.min_cost_flow/v1", ResultIdentity.from_plan(plan))
