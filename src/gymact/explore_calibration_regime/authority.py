from enum import Enum
from .refusal import Refusal
class ActionClass(str,Enum): OBSERVE="OBSERVE"; SELECT="SELECT"; CONSTRUCT="CONSTRUCT"; VERIFY="VERIFY"; DO="DO"
def require(action):
    if action is ActionClass.DO: raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")
    return action
