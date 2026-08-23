from dataclasses import dataclass
from enum import Enum
from .admission import admit_policy
from .collision import collision_classes
from .inventory import ModuleInventory
from .policies import CollectorPolicy
from .receipt import QualificationReceipt
from .storage import select_store
from .subject import Refusal, Subject

class ActionClass(str, Enum):
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    DO = "DO"

@dataclass(frozen=True)
class Qualification:
    receipt: QualificationReceipt
    admitted: bool

def require(action: ActionClass) -> None:
    if action is ActionClass.DO:
        raise Refusal("REFUSED_UNRECEIPTED_ACTUATION")

def qualify(subject: Subject, inventory: ModuleInventory, policy: CollectorPolicy, package_dirs: set[str] | None = None) -> Qualification:
    require(ActionClass.CONSTRUCT)
    result = admit_policy(inventory, policy, package_dirs)
    standing = "PARTIAL_ALIVE" if result.admitted else "BUILD_BROKEN"
    store = select_store(require_durable=True).kind.value
    receipt = QualificationReceipt(subject, policy.value, standing, store, len(collision_classes(inventory)), False)
    return Qualification(receipt, result.admitted)
