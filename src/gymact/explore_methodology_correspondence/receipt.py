from dataclasses import dataclass
import hashlib, json

@dataclass(frozen=True)
class Receipt:
    subject: str
    method: str
    projection: str
    standing: str
    actuation_performed: bool=False
    def digest(self) -> str:
        if self.actuation_performed: raise ValueError('REFUSED_UNRECEIPTED_ACTUATION')
        body=json.dumps(self.__dict__,sort_keys=True,separators=(',',':'))
        return hashlib.sha256(body.encode()).hexdigest()
