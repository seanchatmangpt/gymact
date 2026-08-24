from __future__ import annotations

from dataclasses import dataclass
import re
from .refusal import Refused

_SHA = re.compile(r"^[0-9a-f]{40}$")

@dataclass(frozen=True)
class SolverSubject:
    repository: str
    sha: str
    semantic: str

    def __post_init__(self) -> None:
        if "/" not in self.repository or not _SHA.fullmatch(self.sha):
            raise Refused("INVALID_SUBJECT", f"{self.repository}@{self.sha}")
        if not self.semantic.strip():
            raise Refused("EMPTY_SEMANTIC_IDENTITY")

    @property
    def identity(self) -> str:
        return f"{self.repository}@{self.sha}#{self.semantic}"
