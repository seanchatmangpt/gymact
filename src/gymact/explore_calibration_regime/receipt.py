from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class Receipt:
    payload: dict
    digest: str
def issue(payload):
    body=dict(payload); body["actuation_performed"]=False; body["schema"]="gymact.explore-calibration-regime/1"
    raw=json.dumps(body,sort_keys=True,separators=(",",":")).encode()
    return Receipt(body,hashlib.sha256(raw).hexdigest())
def replay(r):
    if r.payload.get("schema")!="gymact.explore-calibration-regime/1" or r.payload.get("actuation_performed") is not False: return False
    raw=json.dumps(r.payload,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()==r.digest
