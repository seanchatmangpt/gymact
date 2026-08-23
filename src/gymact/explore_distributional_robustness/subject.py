from __future__ import annotations

from dataclasses import dataclass
import re

from .refusals import refuse

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class Subject:
    repository: str
    sha: str
    semantic_digest: str

    def __post_init__(self) -> None:
        if "/" not in self.repository or self.repository.startswith("/"):
            raise refuse("INVALID_SUBJECT", "repository must be owner/name")
        if not _SHA40.fullmatch(self.sha):
            raise refuse("INVALID_SUBJECT", "sha must be exactly 40 lowercase hex characters")
        if not self.semantic_digest:
            raise refuse("INVALID_SUBJECT", "semantic digest is required")

    @property
    def identity(self) -> str:
        return f"{self.repository}@{self.sha}#{self.semantic_digest}"
