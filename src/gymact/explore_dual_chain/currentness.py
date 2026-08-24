from dataclasses import dataclass
from .refusal import DualChainRefusal

@dataclass(frozen=True)
class Generation:
    number: int
    digest: str

def current(items: tuple[Generation, ...]) -> Generation:
    if not items:
        raise DualChainRefusal("NO_GENERATION")
    latest = max(i.number for i in items)
    candidates = {i.digest: i for i in items if i.number == latest}
    if len(candidates) != 1:
        raise DualChainRefusal("DIVERGENT_CURRENT_CERTIFICATE")
    return next(iter(candidates.values()))
