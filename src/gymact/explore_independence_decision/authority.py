from __future__ import annotations

from enum import StrEnum

from .errors import Refused


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit(action: ActionClass, broker: str | None = None) -> str:
    if action is ActionClass.DO:
        if broker != "BRCE":
            raise Refused("UNRECEIPTED_ACTUATION")
        return "BRCE_REQUIRED"
    return f"ADMITTED[{action.value}]"
