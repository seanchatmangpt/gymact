from dataclasses import dataclass


@dataclass(frozen=True)
class Refused(Exception):
    reason: str
    detail: str = ""

    def __str__(self) -> str:
        return f"REFUSED[{self.reason}]" + (f": {self.detail}" if self.detail else "")
