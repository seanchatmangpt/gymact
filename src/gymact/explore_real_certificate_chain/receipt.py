import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Receipt:
    subject: str
    certificate_digest: str
    authority: str = "VERIFY"
    actuation_performed: bool = False

    @property
    def digest(self) -> str:
        body = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode()).hexdigest()
