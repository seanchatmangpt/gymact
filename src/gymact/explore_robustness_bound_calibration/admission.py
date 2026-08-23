from __future__ import annotations

from fractions import Fraction

from .bound import RobustnessBound
from .calibration import Calibration
from .refusal import REFUSED_UNINFORMATIVE_BOUND, Refused


def admit_bound(
    bound: RobustnessBound,
    calibration: Calibration,
    *,
    minimum_coverage: Fraction,
    maximum_mean_width: Fraction,
    maximum_bound_width: Fraction,
) -> None:
    if not calibration.reliable(
        minimum_coverage=minimum_coverage,
        maximum_width=maximum_mean_width,
    ):
        raise Refused(REFUSED_UNINFORMATIVE_BOUND, "calibration unreliable")
    if bound.width > maximum_bound_width:
        raise Refused(REFUSED_UNINFORMATIVE_BOUND, "candidate interval too wide")
