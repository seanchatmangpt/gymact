from __future__ import annotations

from dataclasses import dataclass
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class Refusal(ValueError):
    """Typed fail-closed EXPLORE refusal."""


@dataclass(frozen=True, order=True)
class Subject:
    repo: str
    sha: str

    def __post_init__(self) -> None:
        if not _REPO.fullmatch(self.repo):
            raise Refusal("REFUSED_INVALID_REPOSITORY_IDENTITY")
        if not _SHA.fullmatch(self.sha):
            raise Refusal("REFUSED_INEXACT_SUBJECT_SHA")

    @property
    def identity(self) -> str:
        return f"{self.repo}@{self.sha}"
