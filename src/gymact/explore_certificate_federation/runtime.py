from dataclasses import dataclass
from enum import StrEnum

from .refusal import FederationRefusal


class RuntimeKind(StrEnum):
    BEAM = "BEAM"
    WASM = "WASM"
    NIF = "NIF"
    REMOTE = "REMOTE"
    PLAN = "PLAN"


@dataclass(frozen=True)
class RuntimeProjection:
    kind: RuntimeKind
    implementation_digest: str
    environment_digest: str

    def __post_init__(self) -> None:
        if not self.implementation_digest.strip() or not self.environment_digest.strip():
            raise FederationRefusal("INVALID_RUNTIME_PROJECTION")

    @property
    def identity(self) -> str:
        return f"{self.kind}:{self.implementation_digest}:{self.environment_digest}"
