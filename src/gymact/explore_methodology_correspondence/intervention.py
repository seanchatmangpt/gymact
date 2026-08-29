from dataclasses import dataclass

@dataclass(frozen=True)
class InterventionIntent:
    target: str
    operation: str
    authority: str='CONSTRUCT'

def require_non_actuating(intent: InterventionIntent) -> InterventionIntent:
    if intent.authority == 'DO':
        raise ValueError('REFUSED_UNRECEIPTED_ACTUATION')
    return intent
