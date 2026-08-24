from dataclasses import dataclass
from .refusal import DualChainRefusal

_ALLOWED = frozenset({"BEAM", "WASM", "NIF", "REMOTE", "PLAN"})

@dataclass(frozen=True)
class RuntimeProjection:
    kind: str
    semantic_digest: str
    result_digest: str

    def __post_init__(self) -> None:
        if self.kind not in _ALLOWED or not self.semantic_digest or not self.result_digest:
            raise DualChainRefusal("INVALID_RUNTIME_PROJECTION")

def correspond(a: RuntimeProjection, b: RuntimeProjection) -> bool:
    return a.kind != b.kind and a.semantic_digest == b.semantic_digest and a.result_digest == b.result_digest
