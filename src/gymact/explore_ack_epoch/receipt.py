from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class Receipt:
    payload:dict
    digest:str
def make_receipt(payload:dict)->Receipt:
    body={**payload,"actuation_performed":False,"schema":"gymact.explore-ack-epoch/1"}
    raw=json.dumps(body,sort_keys=True,separators=(",",":")).encode()
    return Receipt(body,hashlib.sha256(raw).hexdigest())
def replay(r:Receipt)->bool:
    if r.payload.get("actuation_performed") is not False: return False
    return make_receipt({k:v for k,v in r.payload.items() if k not in {"actuation_performed","schema"}}).digest==r.digest
