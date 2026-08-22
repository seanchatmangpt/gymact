from dataclasses import dataclass
from .collision import collision_classes
from .inventory import ModuleInventory

@dataclass(frozen=True)
class CollisionTopology:
    components: tuple[tuple[str, ...], ...]

def build_topology(inventory: ModuleInventory) -> CollisionTopology:
    comps = tuple(c.paths for c in collision_classes(inventory))
    return CollisionTopology(components=comps)
