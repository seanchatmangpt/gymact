from dataclasses import dataclass
from fractions import Fraction

from .budget import AcquisitionBudget
from .calibration import RailCalibration
from .capability import RailCapability
from .coverage import Coverage
from .dependence import IndependenceProof
from .knapsack import Selection, select_exact
from .receipt import AcquisitionReceipt, ActionClass, require
from .storage import PersistenceNeed, Store, select
from .strategies import AcquisitionStrategy, Score, score
from .subject import Subject


@dataclass(frozen=True, slots=True)
class AcquisitionPlan:
    strategy: AcquisitionStrategy
    selection: Selection
    coverage: float
    store: Store
    receipt: AcquisitionReceipt


def plan(
    subject: Subject,
    rails: tuple[RailCapability, ...],
    calibrations: tuple[RailCalibration, ...],
    strategy: AcquisitionStrategy,
    budget: AcquisitionBudget,
    required_scope: frozenset[str],
    proofs: tuple[IndependenceProof, ...] = (),
    persistence: PersistenceNeed = PersistenceNeed(),
    prior_fault: Fraction = Fraction(1, 2),
    seed: int = 0,
) -> AcquisitionPlan:
    require(ActionClass.CONSTRUCT)
    calibration_by_rail = {item.rail.fingerprint: item for item in calibrations}
    usable = tuple(
        rail
        for rail in rails
        if rail.subject == subject
        and rail.fingerprint in calibration_by_rail
        and calibration_by_rail[rail.fingerprint].state == "CALIBRATED"
    )
    scores: dict[str, Score] = {}
    total_trials = sum(item.support for item in calibrations)
    for rail in usable:
        scores[rail.fingerprint] = score(
            calibration_by_rail[rail.fingerprint],
            strategy,
            prior_fault,
            total_trials=total_trials,
            seed=seed,
        )
    selection = select_exact(usable, scores, budget, proofs)
    coverage = Coverage(required_scope).ratio(selection.rails)
    store = select(persistence)
    standing = "REQUALIFYING" if selection.rails else "UNKNOWN"
    receipt = AcquisitionReceipt(
        subject=subject,
        strategy=strategy.value,
        rail_fingerprints=tuple(rail.fingerprint for rail in selection.rails),
        store=store.value,
        standing=standing,
    )
    return AcquisitionPlan(strategy, selection, coverage, store, receipt)
