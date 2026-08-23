import re
from dataclasses import dataclass

from .errors import Refused

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Subject:
    repo: str
    sha: str
    semantic_digest: str

    @classmethod
    def parse(cls, repo: str, sha: str, semantic_digest: str) -> "Subject":
        if "/" not in repo or repo.startswith("/") or repo.endswith("/"):
            raise Refused("INVALID_SUBJECT", "repo must be owner/name")
        if not _SHA40.fullmatch(sha):
            raise Refused("INVALID_SUBJECT", "sha must be lowercase 40-hex")
        if not _DIGEST64.fullmatch(semantic_digest):
            raise Refused("INVALID_SUBJECT", "semantic digest must be lowercase 64-hex")
        return cls(repo, sha, semantic_digest)

    @property
    def key(self) -> str:
        return f"{self.repo}@{self.sha}#{self.semantic_digest}"
