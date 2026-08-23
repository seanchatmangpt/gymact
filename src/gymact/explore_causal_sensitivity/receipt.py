import hashlib
import json
from dataclasses import asdict, dataclass

from .authority import ActionClass
from .subject import Subject


@dataclass(frozen=True)
class SensitivityReceipt:
    subject: str
    strategy: str
    standing: str
    action: str = ActionClass.CONSTRUCT.value
    actuation_performed: bool = False

    def canonical_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def make_receipt(subject: Subject, strategy: str, standing: str) -> SensitivityReceipt:
    return SensitivityReceipt(subject.canonical(), strategy, standing)
