from fractions import Fraction

from .realization import AcquisitionRealization

def realized_regret(chosen: AcquisitionRealization, alternatives: list[AcquisitionRealization]) -> Fraction:
    best = max((x.realized_gain for x in [chosen, *alternatives]), default=chosen.realized_gain)
    return best - chosen.realized_gain
