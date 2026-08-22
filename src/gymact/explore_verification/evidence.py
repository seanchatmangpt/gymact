from dataclasses import dataclass
from .subject import Subject

OUTCOMES = {"PASS", "FAIL", "PENDING", "UNKNOWN", "UNSUPPORTED", "BLOCKED"}


@dataclass(frozen=True)
class Evidence:
    subject: Subject
    axis: str
    outcome: str
    detail: str = ""

    def __post_init__(self):
        if self.outcome not in OUTCOMES:
            raise ValueError("REFUSED_INVALID_OUTCOME")
