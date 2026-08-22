from dataclasses import dataclass
from .refusal import Refusal

@dataclass(frozen=True)
class CalibrationRegime:
    source_id: str
    generation: int
    model_digest: str
    state: str
    def __post_init__(self):
        if self.generation < 0: raise Refusal("REFUSED_NEGATIVE_REGIME_GENERATION")
        if self.state not in {"STABLE","DRIFT","INSUFFICIENT"}: raise Refusal("REFUSED_INVALID_REGIME_STATE")

def advance(previous, *, model_digest, state):
    generation=0 if previous is None else previous.generation + (model_digest != previous.model_digest or state != previous.state)
    source_id=previous.source_id if previous else "unknown"
    return CalibrationRegime(source_id,generation,model_digest,state)
