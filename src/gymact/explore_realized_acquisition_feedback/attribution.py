from fractions import Fraction

from .realization import AcquisitionRealization


def leave_one_out_contribution(
    xs: list[AcquisitionRealization], sensor: str
) -> Fraction:
    total = sum((item.realized_gain for item in xs), Fraction(0))
    reduced = sum(
        (item.realized_gain for item in xs if item.sensor != sensor), Fraction(0)
    )
    return total - reduced
