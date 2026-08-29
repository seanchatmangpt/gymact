from __future__ import annotations

from dataclasses import dataclass
import re

_EXACT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


class Refused(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Subject:
    canonical: str

    @classmethod
    def parse(cls, value: str) -> "Subject":
        if not _EXACT.fullmatch(value):
            raise Refused("REFUSED_INEXACT_SUBJECT")
        return cls(value)

    @property
    def sha(self) -> str:
        return self.canonical.rsplit("@", 1)[1]
