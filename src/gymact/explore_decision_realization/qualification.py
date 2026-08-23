from dataclasses import dataclass

from .calibration import DecisionRealizationCalibration
from .decision import DecisionIdentity
from .methodology import require_methodologies
from .receipt import Receipt, manufacture
from .standing import Standing, combine


@dataclass(frozen=True, slots=True)
class Qualification:
    standing: Standing
    receipt: Receipt | None


def qualify(
    decision: DecisionIdentity,
    calibration: DecisionRealizationCalibration,
    strategy: str,
    methodologies: set[str],
    dependencies: tuple[Standing, ...],
    *,
    drifted: bool = False,
) -> Qualification:
    require_methodologies(methodologies)
    standing = combine(
        dependencies,
        realization_admitted=calibration.admitted,
        drifted=drifted,
    )
    if standing in {Standing.BUILD_BROKEN, Standing.BLOCKED}:
        return Qualification(standing, None)
    receipt = manufacture(decision, strategy, standing, calibration.generation)
    return Qualification(standing, receipt)
