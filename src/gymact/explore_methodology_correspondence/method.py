from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
import hashlib, json

class MethodKind(StrEnum):
    DISCOVERY='DISCOVERY'; CONFORMANCE='CONFORMANCE'; SIMULATION='SIMULATION'; PREDICTION='PREDICTION'; OPTIMIZATION='OPTIMIZATION'; INTERVENTION='INTERVENTION'; MONITORING='MONITORING'

@dataclass(frozen=True)
class Method:
    name: str
    kind: MethodKind
    semantics: tuple[str, ...]
    def digest(self) -> str:
        body=json.dumps({'name':self.name,'kind':self.kind,'semantics':sorted(self.semantics)},sort_keys=True,separators=(',',':'))
        return hashlib.sha256(body.encode()).hexdigest()
