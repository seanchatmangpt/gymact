from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    name: str
    capabilities: frozenset[str]
    reversible: bool = True


def discover(items, required: set[str]):
    return tuple(
        sorted(
            (item for item in items if item.reversible and required <= item.capabilities),
            key=lambda item: item.name,
        )
    )
