from dataclasses import dataclass
from datetime import datetime
from .refusal import Refusal

@dataclass(frozen=True)
class Trial:
    source_id: str
    trial_id: str
    actual_pass: bool
    predicted_pass: bool
    observed_at: datetime
    def __post_init__(self):
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise Refusal("REFUSED_NAIVE_TRIAL_TIME")

def admit_trials(trials, *, now):
    seen=set()
    for t in trials:
        key=(t.source_id,t.trial_id)
        if key in seen: raise Refusal("REFUSED_DUPLICATE_TRIAL")
        if t.observed_at > now: raise Refusal("REFUSED_FUTURE_TRIAL")
        seen.add(key)
    return tuple(sorted(trials,key=lambda t:(t.observed_at,t.source_id,t.trial_id)))
