from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RobustnessRefusal(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"REFUSED[{self.code}]: {self.detail}"


def refuse(code: str, detail: str) -> RobustnessRefusal:
    return RobustnessRefusal(code=code, detail=detail)
