from __future__ import annotations

import re
from dataclasses import dataclass

from .refusal import DualityRefusal

_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str
    semantic: str

    @classmethod
    def admit(cls, repo: str, sha: str, semantic: str) -> "Subject":
        if "/" not in repo or not _SHA.fullmatch(sha) or not semantic.strip():
            raise DualityRefusal("INVALID_SUBJECT", f"{repo}@{sha}#{semantic}")
        return cls(repo, sha, semantic)
