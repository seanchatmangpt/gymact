from fractions import Fraction
from .primal import PrimalResult
from .dual import DualResult


def strong_duality(primal: PrimalResult, dual: DualResult) -> Fraction:
    if primal.subject != dual.subject:
        raise ValueError("SUBJECT_DRIFT")
    gap = primal.value - dual.value
    if gap != 0:
        raise ValueError("NONZERO_DUALITY_GAP")
    return gap
