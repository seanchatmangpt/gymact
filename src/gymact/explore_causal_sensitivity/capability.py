from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    BOUNDED_OUTCOME = "BOUNDED_OUTCOME"
    HIDDEN_CONFOUNDING = "HIDDEN_CONFOUNDING"
    EXACT_RATIONAL = "EXACT_RATIONAL"
    REPLAY = "REPLAY"
    TRANSACTIONAL_PERSISTENCE = "TRANSACTIONAL_PERSISTENCE"


@dataclass(frozen=True)
class CapabilitySet:
    values: frozenset[Capability]

    def require(self, *required: Capability) -> None:
        missing = set(required) - set(self.values)
        if missing:
            raise ValueError("missing capabilities: " + ",".join(sorted(x.value for x in missing)))
