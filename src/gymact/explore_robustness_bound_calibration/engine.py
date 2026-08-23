from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .admission import admit_bound
from .bound import RobustnessBound
from .calibration import Calibration
from .frontier import CalibrationSnapshot, require_current
from .geometry import identification_value
from .receipt import Receipt
from .subject import Subject


@dataclass(frozen=True, slots=True)
class Qualification:
    standing: str
    identification_value: Fraction
    receipt: Receipt


def qualify(
    subject: Subject,
    bound: RobustnessBound,
    calibration: Calibration,
    snapshot: CalibrationSnapshot,
    frontier: tuple[CalibrationSnapshot, ...],
    *,
    minimum_coverage: Fraction,
    maximum_mean_width: Fraction,
    maximum_bound_width: Fraction,
    domain_width: Fraction,
) -> Qualification:
    require_current(snapshot, frontier)
    admit_bound(
        bound,
        calibration,
        minimum_coverage=minimum_coverage,
        maximum_mean_width=maximum_mean_width,
        maximum_bound_width=maximum_bound_width,
    )
    value = identification_value(bound, domain_width)
    standing = "PARTIAL_ALIVE"
    return Qualification(standing, value, Receipt.create(subject, snapshot.digest, standing))
