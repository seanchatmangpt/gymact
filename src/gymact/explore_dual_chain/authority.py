from enum import Enum
from .refusal import DualChainRefusal

class Action(str, Enum):
    OBSERVE = "OBSERVE"
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    VERIFY = "VERIFY"
    DO = "DO"

def admit_action(action: Action, broker: str | None = None) -> None:
    if action is Action.DO and broker != "BRCE":
        raise DualChainRefusal("UNRECEIPTED_ACTUATION")
