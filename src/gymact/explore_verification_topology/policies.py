from dataclasses import dataclass
from enum import Enum

class CollectorPolicy(str, Enum):
    IMPORTLIB = "IMPORTLIB"
    PACKAGE_NAMESPACE = "PACKAGE_NAMESPACE"
    UNIQUE_BASENAME = "UNIQUE_BASENAME"
    PATH_HASH_ALIAS = "PATH_HASH_ALIAS"

@dataclass(frozen=True)
class PolicyCapabilities:
    duplicate_basenames: bool
    package_markers_required: bool
    rename_required: bool

CAPABILITIES = {
    CollectorPolicy.IMPORTLIB: PolicyCapabilities(True, False, False),
    CollectorPolicy.PACKAGE_NAMESPACE: PolicyCapabilities(True, True, False),
    CollectorPolicy.UNIQUE_BASENAME: PolicyCapabilities(False, False, True),
    CollectorPolicy.PATH_HASH_ALIAS: PolicyCapabilities(True, False, False),
}
