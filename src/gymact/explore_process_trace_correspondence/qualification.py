from __future__ import annotations

from dataclasses import dataclass

from .equivalence import Equivalence, equivalent
from .oracle import OracleWitness, require_independent
from .receipt import Receipt
from .standing import Standing, classify
from .trace import Trace


@dataclass(frozen=True)
class Qualification:
    standing: Standing
    receipt: Receipt


def qualify(
    reference: Trace,
    candidate: Trace,
    witnesses: tuple[OracleWitness, ...],
    *,
    hard_failure: bool = False,
) -> Qualification:
    require_independent(witnesses)
    exact = equivalent(reference, candidate, Equivalence.EXACT)
    standing = classify(
        refused=False,
        hard_failure=hard_failure,
        exact=exact,
        independent=True,
    )
    receipt = Receipt(reference.subject, Equivalence.EXACT.value, standing)
    return Qualification(standing, receipt)
