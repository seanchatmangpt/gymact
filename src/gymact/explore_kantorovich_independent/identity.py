from __future__ import annotations

import re
from dataclasses import dataclass

from .refusal import IndependentVerifierRefusal

_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class VerificationSubject:
    repo: str
    sha: str
    semantic: str

    @classmethod
    def admit(cls, repo: str, sha: str, semantic: str) -> "VerificationSubject":
        if "/" not in repo or not _SHA.fullmatch(sha) or not semantic.strip():
            raise IndependentVerifierRefusal("INVALID_SUBJECT", f"{repo}@{sha}#{semantic}")
        return cls(repo=repo, sha=sha, semantic=semantic.strip())

    @property
    def identity(self) -> str:
        return f"{self.repo}@{self.sha}#{self.semantic}"
