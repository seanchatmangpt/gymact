"""DfCM EXPLORE control-plane primitives."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Lineage:
    key: str
    base_sha: str
    predecessor_sha: str | None = None

    def admitted_parent(self) -> str:
        return self.predecessor_sha or self.base_sha
