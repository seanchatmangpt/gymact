from __future__ import annotations


class FusionRefused(ValueError):
    """Fail-closed refusal carrying a stable machine reason."""

    def __init__(self, reason: str) -> None:
        if not reason.startswith("REFUSED_"):
            raise ValueError("refusal reason must be typed")
        self.reason = reason
        super().__init__(reason)
