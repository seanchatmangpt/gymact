from fractions import Fraction

from .realization import AcquisitionRealization


def realized_regret(
    chosen: AcquisitionRealization,
    alternatives: list[AcquisitionRealization],
) -> Fraction:
    candidates = [chosen, *alternatives]
    best = max((item.realized_gain for item in candidates), default=chosen.realized_gain)
    return best - chosen.realized_gain
