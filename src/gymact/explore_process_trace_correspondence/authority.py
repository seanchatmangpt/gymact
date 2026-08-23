from __future__ import annotations

from enum import Enum

from .refusal import Refused


class ActionClass(str, Enum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit(action: ActionClass) -> ActionClass:
    if action is ActionClass.DO:
        raise Refused("UNRECEIPTED_ACTUATION")
    return action
