from dataclasses import dataclass
from datetime import datetime
@dataclass(frozen=True, slots=True)
class EvidenceLease:
    issued_at:datetime; expires_at:datetime
    def __post_init__(self):
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None or self.expires_at<=self.issued_at: raise ValueError('REFUSED_INVALID_LEASE')
    def contains(self, now:datetime)->bool:
        if now.tzinfo is None: raise ValueError('REFUSED_NAIVE_TIME')
        return self.issued_at<=now<self.expires_at
