from enum import Enum

class ActionClass(str, Enum):
    OBSERVE="OBSERVE"
    SELECT="SELECT"
    CONSTRUCT="CONSTRUCT"
    VERIFY="VERIFY"
    DO="DO"

def require(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise PermissionError("REFUSED_UNRECEIPTED_ACTUATION")
