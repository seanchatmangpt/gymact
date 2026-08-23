from enum import StrEnum

from .calibration import Calibration
from .independence import IndependenceProof


class FusionTopology(StrEnum):
    HEALTHY = "HEALTHY"
    CORRELATED = "CORRELATED"
    DIVERGENT = "DIVERGENT"
    UNDER_SUPPORTED = "UNDER_SUPPORTED"


def classify(calibrations: tuple[Calibration, ...], proofs: tuple[IndependenceProof, ...], min_support: int = 10) -> FusionTopology:
    if any(c.support < min_support for c in calibrations):
        return FusionTopology.UNDER_SUPPORTED
    required = len(calibrations) * (len(calibrations) - 1) // 2
    if len({p.pair() for p in proofs}) < required:
        return FusionTopology.CORRELATED
    if max((c.error_mass for c in calibrations), default=0) > 1:
        return FusionTopology.DIVERGENT
    return FusionTopology.HEALTHY
