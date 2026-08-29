from __future__ import annotations

from dataclasses import dataclass

from .epoch import SubjectEpoch
from .identity import Refused
from .obligation import ObligationState


@dataclass(frozen=True, slots=True)
class Evidence:
    epoch: SubjectEpoch
    obligation: str
    state: ObligationState
    source_id: str


def admit_evidence(evidence: Evidence, current: SubjectEpoch) -> Evidence:
    if evidence.epoch.subject != current.subject:
        raise Refused("REFUSED_FOREIGN_SUBJECT_EVIDENCE")
    if evidence.epoch.generation != current.generation:
        raise Refused("REFUSED_STALE_OR_FUTURE_EVIDENCE")
    if not evidence.obligation or not evidence.source_id:
        raise Refused("REFUSED_INCOMPLETE_EVIDENCE")
    return evidence
