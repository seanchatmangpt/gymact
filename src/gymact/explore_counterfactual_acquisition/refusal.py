class Refused(ValueError):
    """Typed fail-closed refusal used by the counterfactual acquisition frontier."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        message = code if not detail else f"{code}: {detail}"
        super().__init__(message)
