from fractions import Fraction

from .realization import AcquisitionRealization

def leave_one_out_contribution(xs: list[AcquisitionRealization], sensor: str) -> Fraction:
    total = sum((x.realized_gain for x in xs), Fraction(0))
    reduced = sum((x.realized_gain for x in xs if x.sensor != sensor), Fraction(0))
    return total - reduced
