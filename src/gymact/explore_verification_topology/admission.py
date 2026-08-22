from dataclasses import dataclass
from hashlib import sha256
from .collision import collision_classes
from .inventory import ModuleInventory
from .policies import CollectorPolicy

@dataclass(frozen=True)
class AdmissionResult:
    admitted: bool
    reasons: tuple[str, ...]
    aliases: tuple[tuple[str, str], ...] = ()

def _alias(path: str) -> str:
    return "vtop_" + sha256(path.encode()).hexdigest()[:12]

def admit_policy(inventory: ModuleInventory, policy: CollectorPolicy, package_dirs: set[str] | None = None) -> AdmissionResult:
    collisions = collision_classes(inventory)
    package_dirs = package_dirs or set()
    if policy is CollectorPolicy.IMPORTLIB:
        return AdmissionResult(True, ())
    if policy is CollectorPolicy.UNIQUE_BASENAME:
        return AdmissionResult(not collisions, tuple(f"duplicate:{c.basename}" for c in collisions))
    if policy is CollectorPolicy.PACKAGE_NAMESPACE:
        missing = sorted({m.parent for m in inventory.modules if any(m.path in c.paths for c in collisions)} - package_dirs)
        return AdmissionResult(not missing, tuple(f"missing-package:{p}" for p in missing))
    aliases = tuple((m.path, _alias(m.path)) for m in inventory.modules)
    return AdmissionResult(True, (), aliases)
