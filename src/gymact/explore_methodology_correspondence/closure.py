from dataclasses import dataclass

@dataclass(frozen=True)
class Closure:
    required: frozenset[str]
    observed: frozenset[str]
    @property
    def missing(self) -> frozenset[str]: return self.required-self.observed
    @property
    def complete(self) -> bool: return not self.missing
