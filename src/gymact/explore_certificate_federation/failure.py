from dataclasses import dataclass
from enum import StrEnum
import hashlib


class FailureKind(StrEnum):
    NODE_DOWN = "NODE_DOWN"
    PARTITION = "PARTITION"
    LATENCY = "LATENCY"
    LOSS = "LOSS"
    VERSION_SKEW = "VERSION_SKEW"
    CERTIFICATE_DRIFT = "CERTIFICATE_DRIFT"
    AMBIGUOUS_DO = "AMBIGUOUS_DO"


@dataclass(frozen=True)
class FailureWorld:
    kind: FailureKind
    seed: int

    @property
    def identity(self) -> str:
        return hashlib.sha256(f"{self.kind.value}:{self.seed}".encode()).hexdigest()
