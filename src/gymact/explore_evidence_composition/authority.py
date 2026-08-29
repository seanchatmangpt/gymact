from __future__ import annotations

from enum import StrEnum

from .refusal import RefusalCode, Refused


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit(action: ActionClass, *, broker: str | None = None) -> ActionClass:
    if action is ActionClass.DO and broker != "BRCE":
        raise Refused(RefusalCode.UNRECEIPTED_ACTUATION, "consequential DO requires BRCE")
    return action
