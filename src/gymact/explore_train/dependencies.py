from dataclasses import dataclass

@dataclass(frozen=True)
class DependencyEdge:
    source_repo: str
    source_sha: str
    target_repo: str
    contract: str

    def pinned(self) -> bool:
        return len(self.source_sha) == 40 and all(c in "0123456789abcdef" for c in self.source_sha.lower())
