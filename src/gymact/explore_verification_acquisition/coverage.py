from dataclasses import dataclass

from .capability import RailCapability


@dataclass(frozen=True, slots=True)
class Coverage:
    required: frozenset[str]

    def uncovered(self, rails: tuple[RailCapability, ...]) -> frozenset[str]:
        observed: set[str] = set()
        for rail in rails:
            observed.update(rail.scope)
        return self.required - observed

    def ratio(self, rails: tuple[RailCapability, ...]) -> float:
        if not self.required:
            return 1.0
        return 1.0 - len(self.uncovered(rails)) / len(self.required)
