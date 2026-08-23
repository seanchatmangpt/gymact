from dataclasses import dataclass
from .admission import admit_policy
from .inventory import ModuleInventory
from .migration import plan_migration
from .policies import CollectorPolicy

@dataclass(frozen=True)
class StrategyVector:
    policy: CollectorPolicy
    safety: int
    migration_cost: int
    reversibility: int

def vector(inventory: ModuleInventory, policy: CollectorPolicy, package_dirs: set[str] | None = None) -> StrategyVector:
    admitted = admit_policy(inventory, policy, package_dirs).admitted
    safety = 3 if admitted else 0
    if policy is CollectorPolicy.UNIQUE_BASENAME:
        safety = 4 if admitted else 1
    reversibility = {CollectorPolicy.IMPORTLIB: 4, CollectorPolicy.PACKAGE_NAMESPACE: 3, CollectorPolicy.UNIQUE_BASENAME: 2, CollectorPolicy.PATH_HASH_ALIAS: 4}[policy]
    return StrategyVector(policy, safety, plan_migration(inventory, policy).cost, reversibility)

def pareto(vectors: tuple[StrategyVector, ...]) -> tuple[StrategyVector, ...]:
    def dominates(a: StrategyVector, b: StrategyVector) -> bool:
        better_or_equal = a.safety >= b.safety and a.migration_cost <= b.migration_cost and a.reversibility >= b.reversibility
        strict = a.safety > b.safety or a.migration_cost < b.migration_cost or a.reversibility > b.reversibility
        return better_or_equal and strict
    return tuple(v for v in vectors if not any(dominates(o, v) for o in vectors if o != v))
