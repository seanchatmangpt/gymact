from enum import StrEnum

from .refusal import Refused


class ActionClass(StrEnum):
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    DO = "DO"


def admit_action(action: ActionClass) -> ActionClass:
    if action is ActionClass.DO:
        raise Refused("REFUSED_UNRECEIPTED_ACTUATION")
    return action
