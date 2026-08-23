from enum import StrEnum
from .errors import Refused

class ActionClass(StrEnum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"

def admit(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise Refused("REFUSED_UNRECEIPTED_ACTUATION")
