from dataclasses import dataclass
import re

_EXACT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

@dataclass(frozen=True)
class Subject:
    identity: str
    def __post_init__(self):
        if not _EXACT.fullmatch(self.identity):
            raise ValueError("REFUSED_INEXACT_SUBJECT")
    @property
    def repo(self) -> str:
        return self.identity.split("@",1)[0]
    @property
    def sha(self) -> str:
        return self.identity.rsplit("@",1)[1]
