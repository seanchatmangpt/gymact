from dataclasses import dataclass

@dataclass(frozen=True)
class AuthorityFence:
    allowed_operations: frozenset[str] = frozenset({"SELECT", "CONSTRUCT", "VERIFY"})

    def check(self, operation: str) -> None:
        if operation not in self.allowed_operations:
            raise PermissionError(f"REFUSED_AUTHORITY:{operation}")
