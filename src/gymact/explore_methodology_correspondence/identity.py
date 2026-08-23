from __future__ import annotations

from dataclasses import dataclass
import re

_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class Refusal(ValueError):
    pass


@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str

    def __post_init__(self) -> None:
        if "/" not in self.repo or not _HEX40.fullmatch(self.sha):
            raise Refusal("REFUSED_INEXACT_SUBJECT")

    @property
    def identity(self) -> str:
        return f"{self.repo}@{self.sha}"
