from dataclasses import dataclass
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")

class Refusal(ValueError):
    pass

@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str

    def __post_init__(self) -> None:
        if "/" not in self.repo or not _SHA.fullmatch(self.sha):
            raise Refusal("REFUSED_INEXACT_SUBJECT")
