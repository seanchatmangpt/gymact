import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{40}", self.sha):
            raise ValueError("REFUSED_INEXACT_SUBJECT")
        if "/" not in self.repo:
            raise ValueError("REFUSED_INVALID_REPOSITORY")
