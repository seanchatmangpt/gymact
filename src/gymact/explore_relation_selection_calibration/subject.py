from __future__ import annotations

from dataclasses import dataclass
import re

from .errors import Refused

_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, order=True)
class Subject:
    repo: str
    sha: str
    semantic_digest: str

    def __post_init__(self) -> None:
        if "/" not in self.repo or not _SHA.fullmatch(self.sha):
            raise Refused("INEXACT_SUBJECT", f"{self.repo}@{self.sha}")
        if len(self.semantic_digest) != 64 or any(c not in "0123456789abcdef" for c in self.semantic_digest):
            raise Refused("INVALID_SEMANTIC_DIGEST")

    @property
    def key(self) -> str:
        return f"{self.repo}@{self.sha}"
