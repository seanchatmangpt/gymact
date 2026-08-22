from dataclasses import dataclass, field
from .contracts import CandidateContract

@dataclass
class CandidateRegistry:
    items: dict[str, CandidateContract] = field(default_factory=dict)

    def register(self, candidate: CandidateContract) -> None:
        existing = self.items.get(candidate.name)
        if existing and existing.digest() != candidate.digest():
            raise ValueError("REFUSED_CANDIDATE_IDENTITY_COLLISION")
        self.items[candidate.name] = candidate

    def discover(self, capability: str) -> tuple[CandidateContract, ...]:
        return tuple(sorted((c for c in self.items.values() if capability in c.capabilities), key=lambda c: c.name))
