from dataclasses import dataclass
from collections import defaultdict
from .inventory import ModuleInventory

@dataclass(frozen=True)
class CollisionClass:
    basename: str
    paths: tuple[str, ...]

    @property
    def cardinality(self) -> int:
        return len(self.paths)

def collision_classes(inventory: ModuleInventory) -> tuple[CollisionClass, ...]:
    groups: dict[str, list[str]] = defaultdict(list)
    for m in inventory.modules:
        groups[m.basename].append(m.path)
    return tuple(
        CollisionClass(name, tuple(sorted(paths)))
        for name, paths in sorted(groups.items())
        if len(paths) > 1
    )
