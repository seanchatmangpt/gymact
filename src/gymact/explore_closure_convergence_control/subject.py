from __future__ import annotations

from dataclasses import dataclass
import re

from .refusal import Refused

_SUBJECT = re.compile(r"^(?P<repo>[^/\s]+/[^@\s]+)@(?P<sha>[0-9a-f]{40})$")


@dataclass(frozen=True, slots=True)
class SubjectEpoch:
    repo: str
    sha: str
    generation: int

    @classmethod
    def parse(cls, value: str, generation: int) -> "SubjectEpoch":
        match = _SUBJECT.fullmatch(value)
        if not match:
            raise Refused("INEXACT_SUBJECT", value)
        if generation < 0:
            raise Refused("INVALID_GENERATION", str(generation))
        return cls(match.group("repo"), match.group("sha"), generation)

    @property
    def canonical(self) -> str:
        return f"{self.repo}@{self.sha}#{self.generation}"

    def advance(self, next_sha: str) -> "SubjectEpoch":
        if not re.fullmatch(r"[0-9a-f]{40}", next_sha):
            raise Refused("INEXACT_SUBJECT", next_sha)
        if next_sha == self.sha:
            raise Refused("NONADVANCING_SUBJECT", self.sha)
        return SubjectEpoch(self.repo, next_sha, self.generation + 1)
