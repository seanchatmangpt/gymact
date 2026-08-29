class Refused(ValueError):
    """Typed fail-closed refusal for inadmissible realization evidence."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        message = f"REFUSED[{code}]"
        if detail:
            message += f": {detail}"
        super().__init__(message)
