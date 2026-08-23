from __future__ import annotations

from dataclasses import dataclass
import re

from .refusal import refuse


@dataclass(frozen=True)
class Subject:
    repository: str
    sha: str
    semantic: str

    def __post_init__(self) -> None:
        if "/" not in self.repository:
            refuse("INVALID_SUBJECT", "repository must be owner/name")
        if not re.fullmatch(r"[0-9a-f]{40}", self.sha):
            refuse("INVALID_SUBJECT", "sha must be exact 40-hex")
        if not self.semantic.strip():
            refuse("INVALID_SUBJECT", "semantic identity required")

    @property
    def identity(self) -> str:
        return f"{self.repository}@{self.sha}#{self.semantic}"
