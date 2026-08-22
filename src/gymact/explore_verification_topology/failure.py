from dataclasses import dataclass
import random
from .inventory import ModuleInventory
from .module_identity import TestModule

@dataclass(frozen=True)
class FailureWorld:
    seed: int
    duplicate_count: int

def inject_collisions(inventory: ModuleInventory, world: FailureWorld) -> ModuleInventory:
    rng = random.Random(world.seed)
    modules = list(inventory.modules)
    if not modules:
        return inventory
    for i in range(world.duplicate_count):
        source = rng.choice(modules)
        parent = f"tests/injected_{i}"
        modules.append(TestModule(f"{parent}/{source.basename}"))
    return ModuleInventory.admit(modules)
