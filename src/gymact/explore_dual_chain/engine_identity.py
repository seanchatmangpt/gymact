from dataclasses import dataclass
from .refusal import DualChainRefusal

@dataclass(frozen=True)
class EngineIdentity:
    implementation: str
    model: str
    runtime: str

    def independent_of(self, other: "EngineIdentity") -> bool:
        return self.implementation != other.implementation and self.model != other.model

def require_independent(a: EngineIdentity, b: EngineIdentity) -> None:
    if not a.independent_of(b):
        raise DualChainRefusal("PSEUDO_INDEPENDENT_ENGINE")
