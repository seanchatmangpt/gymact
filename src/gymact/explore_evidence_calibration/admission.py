from __future__ import annotations

from datetime import datetime

from .contracts import Refusal, Subject
from .estimate import CalibrationEstimate
from .witness import CurrentWitness, EvidenceCluster


def admit(
    subject: Subject,
    clusters: tuple[EvidenceCluster, ...],
    witnesses: tuple[CurrentWitness, ...],
    estimates: tuple[CalibrationEstimate, ...],
    *,
    now: datetime,
) -> tuple[dict[str, EvidenceCluster], dict[str, CalibrationEstimate]]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise Refusal("REFUSED_NAIVE_NOW")
    cluster_map = {c.cluster_id: c for c in clusters}
    if len(cluster_map) != len(clusters):
        raise Refusal("REFUSED_DUPLICATE_CLUSTER")
    estimate_map = {e.source_id: e for e in estimates}
    if len(estimate_map) != len(estimates):
        raise Refusal("REFUSED_DUPLICATE_CALIBRATION_ESTIMATE")
    seen: set[str] = set()
    source_cluster: dict[str, str] = {}
    for cluster in clusters:
        for source_id in cluster.source_ids:
            if source_id in source_cluster:
                raise Refusal("REFUSED_OVERLAPPING_SOURCE_CLUSTER")
            source_cluster[source_id] = cluster.cluster_id
    for witness in witnesses:
        if witness.evidence_id in seen:
            raise Refusal("REFUSED_DUPLICATE_EVIDENCE")
        if witness.subject != subject:
            raise Refusal("REFUSED_FOREIGN_SUBJECT_EVIDENCE")
        if witness.observed_at > now:
            raise Refusal("REFUSED_FUTURE_EVIDENCE")
        cluster = cluster_map.get(witness.cluster_id)
        if cluster is None or witness.source_id not in cluster.source_ids:
            raise Refusal("REFUSED_UNGROUNDED_CLUSTER_MEMBERSHIP")
        seen.add(witness.evidence_id)
    return cluster_map, estimate_map
