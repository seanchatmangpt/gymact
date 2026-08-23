from dataclasses import dataclass
from .calibration import Calibration
from .methodology import require_methodologies
from .receipt import Receipt
from .selector import Candidate, Strategy, select
from .standing import Standing, combine
from .subject import Subject

@dataclass(frozen=True)
class Qualification:
    selected: Candidate
    standing: Standing
    receipt: Receipt | None

def qualify(subject: Subject, calibration: Calibration, candidates: tuple[Candidate, ...], strategy: Strategy, methodologies: frozenset[str], dependencies: tuple[Standing, ...], evidence_ids: tuple[str, ...]) -> Qualification:
    require_methodologies(methodologies)
    selected = select(candidates, strategy)
    standing = combine(dependencies)
    if calibration.support < 2 or calibration.coverage < 1:
        standing = Standing.UNKNOWN if standing is not Standing.BUILD_BROKEN else standing
    if standing is Standing.BUILD_BROKEN:
        return Qualification(selected, standing, None)
    if standing is Standing.ALIVE:
        standing = Standing.PARTIAL_ALIVE
    receipt = Receipt(subject, strategy.value, selected.mode.value, standing, evidence_ids)
    return Qualification(selected, standing, receipt)
