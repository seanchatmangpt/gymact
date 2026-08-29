from __future__ import annotations


class Refused(ValueError):
    """Typed fail-closed refusal for trace correspondence admission."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"REFUSED[{code}]" + (f": {detail}" if detail else ""))
