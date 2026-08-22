from dataclasses import dataclass
from .policies import CollectorPolicy
from .subject import Refusal

@dataclass(frozen=True, order=True)
class PlanWitness:
    generation: int
    policy: CollectorPolicy
    digest: str

def current_frontier(witnesses: tuple[PlanWitness, ...]) -> PlanWitness | None:
    if not witnesses:
        return None
    generation = max(w.generation for w in witnesses)
    current = [w for w in witnesses if w.generation == generation]
    identities = {(w.policy, w.digest) for w in current}
    if len(identities) > 1:
        raise Refusal("REFUSED_DIVERGENT_PLAN_FRONTIER")
    return current[0]
