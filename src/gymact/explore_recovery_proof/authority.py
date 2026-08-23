from __future__ import annotations

from enum import StrEnum

from .subject import Refusal


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def require(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")
