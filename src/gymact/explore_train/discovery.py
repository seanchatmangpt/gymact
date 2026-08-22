from dataclasses import dataclass
from .registry import CandidateRegistry

@dataclass(frozen=True)
class CapabilityDiscovery:
    capability: str
    candidate_names: tuple[str, ...]


def discover_capability(registry: CandidateRegistry, capability: str) -> CapabilityDiscovery:
    return CapabilityDiscovery(capability, tuple(c.name for c in registry.discover(capability)))
