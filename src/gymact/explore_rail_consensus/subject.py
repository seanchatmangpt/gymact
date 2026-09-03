import re
from dataclasses import dataclass

_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class Refusal(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Subject:
    repo: str
    sha: str

    def __post_init__(self) -> None:
        if "/" not in self.repo or self.repo.startswith("/") or self.repo.endswith("/"):
            raise Refusal("REFUSED_INVALID_REPOSITORY")
        if not _HEX40.fullmatch(self.sha):
            raise Refusal("REFUSED_INEXACT_SUBJECT")

    @property
    def identity(self) -> str:
        return f"{self.repo}@{self.sha}"
