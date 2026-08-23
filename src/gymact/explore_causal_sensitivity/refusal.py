from dataclasses import dataclass
from enum import StrEnum


class RefusalCode(StrEnum):
    INVALID_GAMMA = "REFUSED_INVALID_GAMMA"
    EMPTY_LOG = "REFUSED_EMPTY_LOG"
    POSITIVITY = "REFUSED_POSITIVITY"
    UNBOUNDED_OUTCOME = "REFUSED_UNBOUNDED_OUTCOME"
    UNRECEIPTED_ACTUATION = "REFUSED_UNRECEIPTED_ACTUATION"


@dataclass(frozen=True)
class Refusal:
    code: RefusalCode
    reason: str


def refuse(code: RefusalCode, reason: str) -> Refusal:
    if not reason.strip():
        raise ValueError("refusal reason must be non-empty")
    return Refusal(code=code, reason=reason.strip())
