"""Exact replay identity index."""
from dataclasses import dataclass,field
@dataclass(slots=True)
class ReplayIndex:
    receipts: dict=field(default_factory=dict)
    def record(self,r)->None:
        old=self.receipts.get(r.replay_key)
        if old is not None and old.identity!=r.identity:raise ValueError("replay_identity_drift")
        self.receipts[r.replay_key]=r
