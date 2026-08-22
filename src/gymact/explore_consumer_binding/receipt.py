from dataclasses import asdict,dataclass
import hashlib,json
from .claim import ConsumptionClaim
@dataclass(frozen=True, slots=True)
class Receipt:
    schema:str; digest:str; actuation_performed:bool=False
def manufacture(claim:ConsumptionClaim,standing:str)->Receipt:
    payload={'claim':asdict(claim),'standing':standing,'actuation_performed':False}
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),default=lambda o:asdict(o)).encode()
    return Receipt('gymact.explore-consumer-binding/1',hashlib.sha256(raw).hexdigest(),False)
def replay(claim,standing,receipt):
    return manufacture(claim,standing)==receipt
