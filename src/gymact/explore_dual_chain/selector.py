from enum import Enum
from .engine_identity import EngineIdentity
from .refusal import DualChainRefusal

class Selector(str, Enum):
    INDEPENDENCE = "independence"
    RUNTIME_DIVERSITY = "runtime_diversity"
    DETERMINISTIC = "deterministic"

def select(engines: tuple[EngineIdentity, ...], strategy: Selector) -> EngineIdentity:
    if not engines:
        raise DualChainRefusal("NO_ENGINE")
    if strategy is Selector.RUNTIME_DIVERSITY:
        return sorted(engines, key=lambda e: (e.runtime, e.implementation))[0]
    if strategy is Selector.INDEPENDENCE:
        return sorted(engines, key=lambda e: (e.implementation, e.model))[0]
    return sorted(engines, key=lambda e: (e.model, e.runtime))[0]
