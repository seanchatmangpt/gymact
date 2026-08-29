from dataclasses import dataclass
import re
from .refusal import DualChainRefusal

_SHA = re.compile(r"^[0-9a-f]{40}$")

@dataclass(frozen=True)
class Subject:
    repo: str
    sha: str
    semantic: str

    def __post_init__(self) -> None:
        if "/" not in self.repo or not _SHA.fullmatch(self.sha) or not self.semantic.strip():
            raise DualChainRefusal("INVALID_SUBJECT")

    @property
    def identity(self) -> str:
        return f"{self.repo}@{self.sha}#{self.semantic}"
