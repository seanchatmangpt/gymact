from dataclasses import dataclass
import re
from .errors import Refused

_SUBJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

@dataclass(frozen=True, order=True)
class SubjectEpoch:
    subject: str
    generation: int

    def __post_init__(self) -> None:
        if not _SUBJECT.fullmatch(self.subject):
            raise Refused("REFUSED_INEXACT_SUBJECT", self.subject)
        if self.generation < 0:
            raise Refused("REFUSED_INVALID_GENERATION")

    def advance(self, subject: str) -> "SubjectEpoch":
        if subject == self.subject:
            raise Refused("REFUSED_NONADVANCING_SUBJECT")
        return SubjectEpoch(subject, self.generation + 1)
