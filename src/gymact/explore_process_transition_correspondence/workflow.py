from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .identity import Refused, Subject
from .obligation import ObligationState


class WorkflowConclusion(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class WorkflowEvidence:
    subject: Subject
    conclusion: WorkflowConclusion


def workflow_state(item: WorkflowEvidence, current: Subject) -> ObligationState:
    if item.subject != current:
        raise Refused("REFUSED_FOREIGN_WORKFLOW_HEAD")
    return {
        WorkflowConclusion.SUCCESS: ObligationState.PASS,
        WorkflowConclusion.FAILURE: ObligationState.FAIL,
        WorkflowConclusion.PENDING: ObligationState.UNKNOWN,
        WorkflowConclusion.UNKNOWN: ObligationState.UNKNOWN,
    }[item.conclusion]
