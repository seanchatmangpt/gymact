from dataclasses import dataclass
from datetime import datetime
import re
_HEX64=re.compile(r"^[0-9a-f]{64}$")
@dataclass(frozen=True)
class Epoch:
    generation:int
    event_id:str
    receipt:str
    observed_at:datetime
    def __post_init__(self):
        if self.generation < 0 or not self.event_id or not _HEX64.fullmatch(self.receipt):
            raise ValueError("REFUSED[INVALID_EPOCH]")
        if self.observed_at.tzinfo is None:
            raise ValueError("REFUSED[NAIVE_EPOCH_TIME]")
