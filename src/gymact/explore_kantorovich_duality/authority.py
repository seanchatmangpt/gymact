from __future__ import annotations

from enum import StrEnum

from .refusal import refuse


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit(action: ActionClass, broker: str | None = None) -> None:
    if action is ActionClass.DO and broker != "BRCE":
        refuse("UNRECEIPTED_ACTUATION", "consequential DO requires BRCE")
