from dataclasses import dataclass

@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    missing: tuple[str, ...]


def check(required: set[str], provided: set[str]) -> CompatibilityResult:
    missing = tuple(sorted(required - provided))
    return CompatibilityResult(not missing, missing)
