from __future__ import annotations
from dataclasses import dataclass
import re

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

class Refusal(ValueError):
    pass

@dataclass(frozen=True, order=True)
class Subject:
    repo: str
    sha: str
    def __post_init__(self) -> None:
        if "/" not in self.repo or not _HEX40.fullmatch(self.sha):
            raise Refusal("REFUSED_INEXACT_SUBJECT")
    @property
    def identity(self) -> str:
        return f"{self.repo}@{self.sha}"

@dataclass(frozen=True)
class Binding:
    producer: Subject
    consumer: Subject
    receipt: str
    schema: str
    scope: str
    binding_id: str
    def __post_init__(self) -> None:
        if not _HEX64.fullmatch(self.receipt) or not self.schema.strip() or not self.binding_id.strip():
            raise Refusal("REFUSED_MALFORMED_BINDING")
        if self.scope not in {"FOCUSED", "INTEGRATION", "REPOSITORY"}:
            raise Refusal("REFUSED_INVALID_SCOPE")
