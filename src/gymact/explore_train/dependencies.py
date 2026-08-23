from dataclasses import dataclass


@dataclass(frozen=True)
class DependencyEdge:
    source_repo: str
    source_sha: str
    target_repo: str
    contract: str

    def pinned(self) -> bool:
        valid_chars = all(char in "0123456789abcdef" for char in self.source_sha.lower())
        return len(self.source_sha) == 40 and valid_chars
