from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn


@dataclass(frozen=True, slots=True)
class Refused(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"REFUSED[{self.code}]: {self.detail}"


def refuse(code: str, detail: str) -> NoReturn:

    raise Refused(code, detail)
