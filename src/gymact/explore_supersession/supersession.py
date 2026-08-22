from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .evidence import Evidence
from .subject import Refusal


class SupersessionReason(str, Enum):
    NEW_HEAD = "NEW_HEAD"
    NEW_RUN = "NEW_RUN"
    NEW_ARTIFACT = "NEW_ARTIFACT"
    NEW_RECEIPT = "NEW_RECEIPT"
    CORRECTION = "CORRECTION"


@dataclass(frozen=True)
class Supersession:
    older: Evidence
    newer: Evidence
    reason: SupersessionReason

    def __post_init__(self) -> None:
        if self.older.subject.repo != self.newer.subject.repo:
            raise Refusal("REFUSED_CROSS_REPOSITORY_SUPERSESSION")
        if self.newer.epoch <= self.older.epoch:
            raise Refusal("REFUSED_NON_FORWARD_SUPERSESSION")
        if self.older.scope != self.newer.scope:
            raise Refusal("REFUSED_INCOMPATIBLE_SUPERSESSION_SCOPE")
