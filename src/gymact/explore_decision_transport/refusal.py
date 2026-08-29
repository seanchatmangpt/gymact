from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Refused(Exception):
    code: str
    detail: str = ""

    def __str__(self) -> str:
        return f"REFUSED[{self.code}]" + (f": {self.detail}" if self.detail else "")
