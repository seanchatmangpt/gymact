import json
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class Receipt:
    subject: str
    operation: str
    input_digest: str
    output_digest: str

    def digest(self) -> str:
        raw = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode()).hexdigest()


def digest_value(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode()).hexdigest()
