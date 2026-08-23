from __future__ import annotations

import re
from dataclasses import dataclass

from .refusal import require

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class Subject:
    repository: str
    sha: str
    semantic_digest: str

    def __post_init__(self) -> None:
        require("/" in self.repository, "INVALID_SUBJECT", "repository must be owner/name")
        require(bool(_SHA40.fullmatch(self.sha)), "INVALID_SUBJECT", "sha must be exact 40-hex")
        require(len(self.semantic_digest) >= 16, "INVALID_SUBJECT", "semantic digest too short")

    @property
    def identity(self) -> str:
        return f"{self.repository}@{self.sha}#{self.semantic_digest}"
