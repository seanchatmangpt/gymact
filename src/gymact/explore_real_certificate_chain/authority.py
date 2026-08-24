from enum import StrEnum


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit(action: ActionClass, broker: str | None = None) -> None:
    if action is ActionClass.DO and broker != "BRCE":
        raise PermissionError("UNRECEIPTED_ACTUATION")
