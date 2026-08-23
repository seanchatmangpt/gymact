from __future__ import annotations

import re
from dataclasses import dataclass

from .refusal import RefusalCode, Refused

_SUBJECT = re.compile(r"^(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<sha>[0-9a-f]{40})#(?P<semantic>[0-9a-f]{64})$")


@dataclass(frozen=True, slots=True)
class Subject:
    repo: str
    sha: str
    semantic_digest: str

    @classmethod
    def parse(cls, value: str) -> "Subject":
        match = _SUBJECT.fullmatch(value)
        if match is None:
            raise Refused(RefusalCode.INVALID_SUBJECT, "expected owner/repo@40hex#64hex")
        return cls(match["repo"], match["sha"], match["semantic"])

    @property
    def key(self) -> str:
        return f"{self.repo}@{self.sha}#{self.semantic_digest}"
