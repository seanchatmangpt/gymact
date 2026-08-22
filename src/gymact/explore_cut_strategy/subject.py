from dataclasses import dataclass
import re

_EXACT = re.compile(r"^[^/\s]+/[^@\s]+@[0-9a-f]{40}$")

@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str

    @classmethod
    def parse(cls, value: str) -> "Subject":
        if not _EXACT.fullmatch(value):
            raise ValueError("REFUSED_INEXACT_SUBJECT")
        repo, sha = value.split("@", 1)
        return cls(repo=repo, sha=sha)

    @property
    def key(self) -> str:
        return f"{self.repo}@{self.sha}"
