from __future__ import annotations

from enum import StrEnum

from .refusal import Refused


class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"


def admit(action: ActionClass) -> ActionClass:
    if action is ActionClass.DO:
        raise Refused("UNRECEIPTED_ACTUATION")
    return action
