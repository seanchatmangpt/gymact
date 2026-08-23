from dataclasses import dataclass
from datetime import datetime
KINDS=("DELIVERY","ACK","DISCHARGE")
@dataclass(frozen=True)
class Witness:
    consumer:str
    generation:int
    event_id:str
    kind:str
    witness_id:str
    observed_at:datetime
    parent_id:str|None=None
    def __post_init__(self):
        if self.kind not in KINDS or self.generation < 0 or not self.consumer or not self.witness_id:
            raise ValueError("REFUSED[INVALID_WITNESS]")
        if self.observed_at.tzinfo is None:
            raise ValueError("REFUSED[NAIVE_WITNESS_TIME]")
