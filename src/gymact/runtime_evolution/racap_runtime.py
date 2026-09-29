"""Paired-world RACaP promotion."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PairedWorld:
    subject: str
    baseline: float
    challenger: float

    @property
    def delta(self) -> float:
        return self.challenger - self.baseline

    def promotes(self, margin: float = 0.0) -> bool:
        return self.delta > margin
