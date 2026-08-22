from dataclasses import dataclass
from fractions import Fraction
from .collision import collision_classes
from .inventory import ModuleInventory

@dataclass(frozen=True)
class TopologyMetrics:
    collision_modules: int
    collision_classes: int
    collision_density: Fraction
    max_class_fraction: Fraction

def measure(inventory: ModuleInventory) -> TopologyMetrics:
    classes = collision_classes(inventory)
    n = len(inventory.modules)
    colliding = sum(c.cardinality for c in classes)
    maxc = max((c.cardinality for c in classes), default=0)
    return TopologyMetrics(colliding, len(classes), Fraction(colliding, n or 1), Fraction(maxc, n or 1))
