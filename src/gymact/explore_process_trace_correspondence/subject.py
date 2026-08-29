from __future__ import annotations

import re
from dataclasses import dataclass

from .refusal import Refused

_SUBJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


@dataclass(frozen=True, order=True)
class Subject:
    identity: str

    def __post_init__(self) -> None:
        if not _SUBJECT.fullmatch(self.identity):
            raise Refused("INEXACT_SUBJECT", self.identity)

    @property
    def sha(self) -> str:
        return self.identity.rsplit("@", 1)[1]
