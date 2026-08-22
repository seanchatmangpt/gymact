from __future__ import annotations

from dataclasses import dataclass
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class Subject:
    repo: str
    sha: str
    ref: str | None = None

    def __post_init__(self) -> None:
        if "/" not in self.repo or self.repo.startswith("/") or self.repo.endswith("/"):
            raise ValueError("REFUSED_INVALID_REPOSITORY_IDENTITY")
        if not _SHA.fullmatch(self.sha):
            raise ValueError("REFUSED_INEXACT_SUBJECT_SHA")

    @property
    def identity(self) -> str:
        return f"{self.repo}@{self.sha}"
