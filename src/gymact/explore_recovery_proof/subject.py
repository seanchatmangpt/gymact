from __future__ import annotations

import re
from dataclasses import dataclass

_EXACT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")


class Refusal(ValueError):
    """Typed fail-closed refusal for recovery-proof admission."""


@dataclass(frozen=True, slots=True)
class Subject:
    identity: str

    def __post_init__(self) -> None:
        if not _EXACT.fullmatch(self.identity):
            raise Refusal("REFUSED_INEXACT_SUBJECT")

    @property
    def repo(self) -> str:
        return self.identity.rsplit("@", 1)[0]

    @property
    def sha(self) -> str:
        return self.identity.rsplit("@", 1)[1]
