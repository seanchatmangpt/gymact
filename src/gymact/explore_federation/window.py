from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Window:
    since: datetime
    until: datetime
    def __post_init__(self):
        if self.since.tzinfo is None or self.until.tzinfo is None or self.since >= self.until:
            raise ValueError("REFUSED_INVALID_WINDOW")
    def contains(self, ts:datetime)->bool:
        if ts.tzinfo is None:
            raise ValueError("REFUSED_NAIVE_TIME")
        return self.since <= ts < self.until
