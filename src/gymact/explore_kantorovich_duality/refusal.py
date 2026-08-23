from __future__ import annotations


class DualityRefusal(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"REFUSED[{code}]: {detail}")
