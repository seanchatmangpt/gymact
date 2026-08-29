from enum import StrEnum

from .errors import Refused


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit(action: ActionClass, broker: str | None = None) -> ActionClass:
    if action is ActionClass.DO and broker != "BRCE":
        raise Refused("UNRECEIPTED_ACTUATION")
    return action
