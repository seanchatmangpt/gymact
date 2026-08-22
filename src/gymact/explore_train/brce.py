from dataclasses import dataclass

@dataclass(frozen=True)
class ConstructIntent:
    capability: str
    payload: dict
    authority_ref: str | None = None

    def consequential(self) -> bool:
        return self.authority_ref is not None


def require_brce(operation: str, via_brce: bool) -> None:
    if operation == "DO" and not via_brce:
        raise PermissionError("REFUSED_UNRECEIPTED_ACTUATION")
