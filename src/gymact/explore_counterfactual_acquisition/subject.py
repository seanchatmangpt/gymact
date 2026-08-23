from dataclasses import dataclass
import re

from .refusal import Refused

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class Subject:
    repository: str
    sha: str

    def __post_init__(self) -> None:
        if self.repository.count("/") != 1 or any(not part for part in self.repository.split("/")):
            raise Refused("REFUSED_INVALID_SUBJECT", self.repository)
        if not _SHA40.fullmatch(self.sha):
            raise Refused("REFUSED_INEXACT_SUBJECT", self.sha)

    @classmethod
    def parse(cls, value: str) -> "Subject":
        try:
            repository, sha = value.rsplit("@", 1)
        except ValueError as exc:
            raise Refused("REFUSED_INVALID_SUBJECT", value) from exc
        return cls(repository=repository, sha=sha)

    @property
    def exact(self) -> str:
        return f"{self.repository}@{self.sha}"
