import re
from dataclasses import dataclass

_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str
    ref: str

    def __post_init__(self) -> None:
        if "/" not in self.repo or not _SHA.fullmatch(self.sha):
            raise ValueError("REFUSED_INEXACT_SUBJECT")
