from datetime import datetime
from .admission import admit
from .candidates import admissible,discover
from .receipt import manufacture
from .selection import select
def qualify(claim,evidence,lease,now:datetime,current_receipt,current_schema):
    admit(claim,evidence,lease,now,current_receipt,current_schema)
    candidate=select(admissible(discover()))
    standing='BUILD_BROKEN' if evidence.standing=='BUILD_BROKEN' else 'PARTIAL_ALIVE'
    return {'candidate':candidate.name,'standing':standing,'receipt':manufacture(claim,standing),'actuation_performed':False}
def require_do(brce_receipt:bool):
    if not brce_receipt: raise PermissionError('REFUSED_UNRECEIPTED_ACTUATION')
    raise PermissionError('REFUSED_EXPLORE_DO_OUT_OF_SCOPE')
