from __future__ import annotations

from dataclasses import dataclass
import re

_SUBJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

@dataclass(frozen=True)
class Subject:
    value: str

    def __post_init__(self) -> None:
        if not _SUBJECT.fullmatch(self.value):
            raise ValueError("REFUSED[INEXACT_SUBJECT]")
