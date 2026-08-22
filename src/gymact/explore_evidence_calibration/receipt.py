from __future__ import annotations
from dataclasses import dataclass
import hashlib,json
SCHEMA="gymact.explore-evidence-calibration/1"
@dataclass(frozen=True)
class QualificationReceipt:
    payload:dict[str,object]; digest:str

def issue(payload:dict[str,object])->QualificationReceipt:
    body=dict(payload); body["schema"]=SCHEMA; body["actuation_performed"]=False
    canonical=json.dumps(body,sort_keys=True,separators=(",",":")).encode()
    return QualificationReceipt(body,hashlib.sha256(canonical).hexdigest())

def replay(receipt:QualificationReceipt)->bool:
    if receipt.payload.get("schema")!=SCHEMA or receipt.payload.get("actuation_performed") is not False: return False
    canonical=json.dumps(receipt.payload,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(canonical).hexdigest()==receipt.digest
