from dataclasses import dataclass
from enum import StrEnum

from .calibration import RailCalibration
from .clusters import EvidenceCluster
from .observation import Outcome


class ConsensusStrategy(StrEnum):
    ALL_INDEPENDENT = "ALL_INDEPENDENT"
    QUORUM_CALIBRATED = "QUORUM_CALIBRATED"
    MINIMAX_FAILURE = "MINIMAX_FAILURE"


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    strategy: ConsensusStrategy
    standing: str
    pass_clusters: int
    fail_clusters: int
    calibrated_pass_clusters: int


def evaluate(
    clusters: tuple[EvidenceCluster, ...],
    calibrations: dict[str, RailCalibration],
    strategy: ConsensusStrategy,
) -> ConsensusResult:
    fail_clusters = 0
    pass_clusters = 0
    calibrated_pass = 0
    for cluster in clusters:
        outcomes = cluster.outcome_set
        if Outcome.FAIL.value in outcomes:
            fail_clusters += 1
            continue
        if outcomes == {Outcome.PASS.value}:
            pass_clusters += 1
            best = any(
                calibrations.get(obs.rail.fingerprint)
                and calibrations[obs.rail.fingerprint].state() == "CALIBRATED"
                for obs in cluster.members
            )
            calibrated_pass += int(best)
    if fail_clusters:
        standing = "BUILD_BROKEN"
    elif strategy is ConsensusStrategy.ALL_INDEPENDENT:
        standing = (
            "PARTIAL_ALIVE"
            if clusters and pass_clusters == len(clusters) and len(clusters) >= 2
            else "UNKNOWN"
        )
    elif strategy is ConsensusStrategy.QUORUM_CALIBRATED:
        standing = "PARTIAL_ALIVE" if calibrated_pass >= 2 else "UNKNOWN"
    else:
        standing = "PARTIAL_ALIVE" if pass_clusters >= 2 and fail_clusters == 0 else "UNKNOWN"
    return ConsensusResult(strategy, standing, pass_clusters, fail_clusters, calibrated_pass)
