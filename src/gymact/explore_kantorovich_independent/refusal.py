from __future__ import annotations


class IndependentVerifierRefusal(ValueError):
    """Typed fail-closed refusal for the independent Kantorovich verifier."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"REFUSED[{code}]: {detail}")
