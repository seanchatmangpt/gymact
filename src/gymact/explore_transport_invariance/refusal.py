from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Refusal(Exception):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"REFUSED[{self.code}]: {self.detail}"


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise Refusal(code, detail)
