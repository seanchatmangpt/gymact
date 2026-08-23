from __future__ import annotations

import re
from dataclasses import dataclass

from .refusal import Refused

_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

@dataclass(frozen=True, order=True)
class Subject:
    repo: str
    sha: str
    semantic: str

    def __post_init__(self) -> None:
        if not _REPO.fullmatch(self.repo):
            raise Refused("INVALID_REPOSITORY", self.repo)
        if not _SHA.fullmatch(self.sha):
            raise Refused("INVALID_SUBJECT_SHA", self.sha)
        if not self.semantic.strip():
            raise Refused("EMPTY_SEMANTIC_IDENTITY")
