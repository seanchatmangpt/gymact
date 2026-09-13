from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Refused(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"REFUSED[{self.code}]: {self.detail}"


def refuse(code: str, detail: str) -> "NoReturn":
    from typing import NoReturn

    raise Refused(code, detail)
