from __future__ import annotations

import re
from dataclasses import dataclass


_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, order=True)
class Subject:
    repo: str
    sha: str
    role: str

    def __post_init__(self) -> None:
        if "/" not in self.repo or not _SHA.fullmatch(self.sha):
            raise ValueError("REFUSED_INVALID_SUBJECT_IDENTITY")
        if self.role not in {"producer", "consumer"}:
            raise ValueError("REFUSED_INVALID_SUBJECT_ROLE")

    @property
    def key(self) -> str:
        return f"{self.repo}@{self.sha}:{self.role}"
