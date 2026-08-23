from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import require

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, order=True)
class Subject:
    repo: str
    sha: str
    semantic_digest: str

    @classmethod
    def parse(cls, repo: str, sha: str, semantic_digest: str) -> "Subject":
        require("/" in repo and not repo.startswith("/"), "INVALID_REPO")
        require(bool(_SHA.fullmatch(sha)), "INVALID_SHA")
        require(bool(_DIGEST.fullmatch(semantic_digest)), "INVALID_SEMANTIC_DIGEST")
        return cls(repo, sha, semantic_digest)

    @property
    def key(self) -> str:
        return f"{self.repo}@{self.sha}#{self.semantic_digest}"
