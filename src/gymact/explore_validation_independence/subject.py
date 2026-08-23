import re
from dataclasses import dataclass
from .refusal import Refused

_SUBJECT = re.compile(r"^(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<sha>[0-9a-f]{40})#(?P<semantic>[0-9a-f]{64})$")

@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str
    semantic: str

    @classmethod
    def parse(cls, value: str) -> "Subject":
        match = _SUBJECT.fullmatch(value)
        if not match:
            raise Refused("INVALID_SUBJECT", value)
        return cls(**match.groupdict())

    @property
    def key(self) -> str:
        return f"{self.repo}@{self.sha}#{self.semantic}"
