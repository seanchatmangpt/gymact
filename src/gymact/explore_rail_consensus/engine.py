from dataclasses import dataclass

from .calibration import RailCalibration
from .clusters import correlated_clusters
from .consensus import ConsensusResult, ConsensusStrategy, evaluate
from .metrics import ConsensusMetrics, measure
from .observation import RailObservation
from .receipt import ActionClass, QualificationReceipt, require
from .relation import IndependenceProof
from .storage import PersistenceNeed, Store, select
from .subject import Subject


@dataclass(frozen=True, slots=True)
class Qualification:
    result: ConsensusResult
    metrics: ConsensusMetrics
    store: Store
    receipt: QualificationReceipt


def qualify(
    subject: Subject,
    observations: tuple[RailObservation, ...],
    calibrations: dict[str, RailCalibration],
    strategy: ConsensusStrategy,
    proofs: tuple[IndependenceProof, ...] = (),
    persistence: PersistenceNeed = PersistenceNeed(),
) -> Qualification:
    require(ActionClass.CONSTRUCT)
    clusters = correlated_clusters(observations, proofs)
    metrics = measure(clusters)
    result = evaluate(clusters, calibrations, strategy)
    store = select(persistence)
    receipt = QualificationReceipt(
        subject=subject,
        strategy=strategy.value,
        standing=result.standing,
        cluster_count=metrics.cluster_count,
        store=store.value,
    )
    return Qualification(result, metrics, store, receipt)
