from __future__ import annotations

from dataclasses import dataclass
import re

from .refusal import Refused, REFUSED_INEXACT_SUBJECT

_SUBJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class Subject:
    value: str

    def __post_init__(self) -> None:
        if not _SUBJECT.fullmatch(self.value):
            raise Refused(REFUSED_INEXACT_SUBJECT, self.value)

    @property
    def sha(self) -> str:
        return self.value.rsplit("@", 1)[1]
