from fractions import Fraction

from .dual import DualResult
from .primal import PrimalResult


def strong_duality(primal: PrimalResult, dual: DualResult) -> Fraction:
    if primal.subject != dual.subject:
        raise ValueError("SUBJECT_DRIFT")
    gap = primal.value - dual.value
    if gap != 0:
        raise ValueError("NONZERO_DUALITY_GAP")
    return gap
