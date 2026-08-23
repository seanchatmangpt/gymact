from dataclasses import dataclass
from .subject import Subject
@dataclass(frozen=True, slots=True)
class ConsumptionClaim:
    consumer:Subject; producer:Subject; component:str; receipt:str; required_scope:str
    def __post_init__(self):
        if not self.component.strip(): raise ValueError('REFUSED_EMPTY_COMPONENT')
