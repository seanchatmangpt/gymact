from __future__ import annotations

from dataclasses import dataclass

from .identity import Refused, Subject


@dataclass(frozen=True, slots=True)
class SubjectEpoch:
    subject: Subject
    generation: int

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise Refused("REFUSED_NEGATIVE_GENERATION")

    def successor(self, subject: Subject) -> "SubjectEpoch":
        if subject == self.subject:
            raise Refused("REFUSED_NONADVANCING_SUBJECT")
        return SubjectEpoch(subject, self.generation + 1)
