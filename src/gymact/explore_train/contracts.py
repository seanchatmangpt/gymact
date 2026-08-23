import json
from dataclasses import dataclass, field
from hashlib import sha256


@dataclass(frozen=True)
class CandidateContract:
    name: str
    capabilities: tuple[str, ...]
    reversible: bool = True
    metadata: dict[str, str] = field(default_factory=dict)

    def digest(self) -> str:
        payload = {
            "name": self.name,
            "capabilities": self.capabilities,
            "reversible": self.reversible,
            "metadata": self.metadata,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode()).hexdigest()
