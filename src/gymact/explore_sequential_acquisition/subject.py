from dataclasses import dataclass
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")


class RefusedValue(ValueError):
    pass


@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str

    def __post_init__(self) -> None:
        if "/" not in self.repo or not _SHA.fullmatch(self.sha):
            raise RefusedValue("REFUSED_INEXACT_SUBJECT")

    @property
    def identity(self) -> str:
        return f"{self.repo}@{self.sha}"
