from dataclasses import dataclass
import re
_SHA=re.compile(r"^[0-9a-f]{40}$")
@dataclass(frozen=True)
class Subject:
    repo:str
    sha:str
    def __post_init__(self):
        if "/" not in self.repo or not _SHA.fullmatch(self.sha):
            raise ValueError("REFUSED[INEXACT_SUBJECT]")
    @property
    def identity(self)->str:
        return f"{self.repo}@{self.sha}"
