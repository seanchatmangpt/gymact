from dataclasses import dataclass
from .refusal import Refusal

@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str
    def __post_init__(self):
        if "/" not in self.repo or len(self.sha) != 40 or any(c not in "0123456789abcdef" for c in self.sha):
            raise Refusal("REFUSED_INEXACT_SUBJECT")
