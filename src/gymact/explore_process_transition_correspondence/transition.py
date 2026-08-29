from __future__ import annotations

from dataclasses import dataclass

from .epoch import SubjectEpoch
from .identity import Refused


@dataclass(frozen=True, slots=True)
class Transition:
    before: SubjectEpoch
    after: SubjectEpoch

    def __post_init__(self) -> None:
        if self.after.generation != self.before.generation + 1:
            raise Refused("REFUSED_NONCONTIGUOUS_TRANSITION")
        if self.after.subject == self.before.subject:
            raise Refused("REFUSED_NONADVANCING_TRANSITION")
