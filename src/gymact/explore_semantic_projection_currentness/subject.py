from __future__ import annotations

import re
from dataclasses import dataclass

_SHA = re.compile(r"^[0-9a-f]{40}$")


class Refusal(ValueError):
    """Typed fail-closed EXPLORE refusal."""


@dataclass(frozen=True, slots=True)
class Subject:
    repository: str
    sha: str

    def __post_init__(self) -> None:
        invalid_repository = (
            "/" not in self.repository
            or self.repository.startswith("/")
            or self.repository.endswith("/")
        )
        if invalid_repository:
            raise Refusal("REFUSED_INVALID_REPOSITORY_IDENTITY")
        if not _SHA.fullmatch(self.sha):
            raise Refusal("REFUSED_INEXACT_SUBJECT")

    @property
    def identity(self) -> str:
        return f"{self.repository}@{self.sha}"
