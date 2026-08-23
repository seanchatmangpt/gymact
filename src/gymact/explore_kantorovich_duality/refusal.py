from __future__ import annotations


class DualityRefusal(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"REFUSED[{code}]: {detail}")
        self.code = code
        self.detail = detail


def refuse(code: str, detail: str) -> None:
    raise DualityRefusal(code, detail)
