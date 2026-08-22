from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Phase(StrEnum):
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    DO = "DO"


@dataclass(frozen=True)
class Authority:
    role: str
    phases: frozenset[Phase]


def admit_phase(authority: Authority, phase: Phase) -> None:
    if phase is Phase.DO:
        raise PermissionError("REFUSED_UNRECEIPTED_ACTUATION")
    if phase not in authority.phases:
        raise PermissionError(f"REFUSED_UNAUTHORIZED_{phase.value}")
