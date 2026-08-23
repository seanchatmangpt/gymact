from __future__ import annotations

from enum import Enum

from .refusal import DualityRefusal


class ActionClass(str, Enum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit_action(action: ActionClass, broker: str | None = None) -> None:
    if action is ActionClass.DO and broker != "BRCE":
        raise DualityRefusal("UNRECEIPTED_ACTUATION", "consequential DO requires BRCE")
