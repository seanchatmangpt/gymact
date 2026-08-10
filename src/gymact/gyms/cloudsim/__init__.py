"""Open-ended, deterministic cloud control-plane simulation for GymAct.

The package models cloud API consequences through a finite semantic algebra. It is
not an AWS/Azure/GCP wire-protocol emulator and performs no cloud SDK or network I/O.
"""

from .capabilities import CLOUDS, CLOUDSIM_CAPABILITIES
from .catalog import SERVICE_FAMILIES, service_catalog_size
from .contracts import CloudOperation, Effect
from .environment import CloudSimEnvironment
from .provider import CloudSimProvider
from .topology import DEFAULT_GLOBAL_TOPOLOGY

__all__ = [
    "CLOUDS",
    "CLOUDSIM_CAPABILITIES",
    "DEFAULT_GLOBAL_TOPOLOGY",
    "SERVICE_FAMILIES",
    "CloudOperation",
    "CloudSimEnvironment",
    "CloudSimProvider",
    "Effect",
    "service_catalog_size",
]
