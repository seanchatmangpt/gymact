from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .oracle_adapter import OracleObservation
from .primal_adapter import SolverObservation
from .refusal import Refused


@dataclass(frozen=True)
class Correspondence:
    subject_identity: str
    primal_engine: str
    oracle_engine: str
    cost_gap: Fraction
    same_shipments: bool


def compare(primal: SolverObservation, oracle: OracleObservation) -> Correspondence:
    if primal.subject != oracle.subject:
        raise Refused("SUBJECT_DIVERGENCE")
    if primal.engine == oracle.engine:
        raise Refused("PSEUDO_INDEPENDENT_ENGINE")
    gap = abs(primal.result.cost - oracle.result.cost)
    if gap:
        raise Refused("OPTIMAL_VALUE_DIVERGENCE", str(gap))
    return Correspondence(
        primal.subject.identity,
        primal.engine,
        oracle.engine,
        gap,
        primal.result.shipments == oracle.result.shipments,
    )
