from __future__ import annotations


class Refused(ValueError):
    """Typed fail-closed refusal used by the EXPLORE candidate graph."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)
