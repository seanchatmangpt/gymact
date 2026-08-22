from dataclasses import dataclass
from pathlib import PurePosixPath
from .collision import collision_classes
from .inventory import ModuleInventory
from .policies import CollectorPolicy

@dataclass(frozen=True)
class Edit:
    path: str
    action: str
    value: str

@dataclass(frozen=True)
class MigrationPlan:
    policy: CollectorPolicy
    edits: tuple[Edit, ...]

    @property
    def cost(self) -> int:
        return len(self.edits)

def plan_migration(inventory: ModuleInventory, policy: CollectorPolicy) -> MigrationPlan:
    collisions = collision_classes(inventory)
    if policy is CollectorPolicy.IMPORTLIB:
        return MigrationPlan(policy, (Edit("pyproject.toml", "set", "--import-mode=importlib"),))
    if policy is CollectorPolicy.PACKAGE_NAMESPACE:
        dirs = sorted({PurePosixPath(p).parent.as_posix() for c in collisions for p in c.paths})
        return MigrationPlan(policy, tuple(Edit(f"{d}/__init__.py", "create", "") for d in dirs))
    if policy is CollectorPolicy.UNIQUE_BASENAME:
        edits = []
        for c in collisions:
            for i, p in enumerate(c.paths[1:], start=1):
                q = PurePosixPath(p)
                edits.append(Edit(p, "rename", str(q.with_name(f"{q.stem}_{i}{q.suffix}"))))
        return MigrationPlan(policy, tuple(edits))
    return MigrationPlan(policy, ())
