from dataclasses import dataclass
from datetime import datetime
from .refusal import Refusal

@dataclass(frozen=True)
class CalibrationWindow:
    start: datetime
    end: datetime
    def __post_init__(self):
        if self.start.tzinfo is None or self.end.tzinfo is None or not self.start < self.end:
            raise Refusal("REFUSED_INVALID_WINDOW")
    def contains(self, t: datetime) -> bool:
        return self.start <= t < self.end
