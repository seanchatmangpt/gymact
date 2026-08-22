from dataclasses import dataclass
from datetime import datetime
from typing import Any
from .subject import Subject

VALID={"PASS","FAIL","PENDING","UNKNOWN","UNSUPPORTED"}
@dataclass(frozen=True)
class Observation:
    subject:Subject
    kind:str
    outcome:str
    observed_at:datetime
    payload:Any=None
    def __post_init__(self):
        if self.outcome not in VALID:
            raise ValueError("REFUSED_UNKNOWN_OUTCOME")
