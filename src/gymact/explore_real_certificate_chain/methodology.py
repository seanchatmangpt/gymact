from dataclasses import dataclass


REQUIRED = frozenset({"discovery","conformance","simulation","prediction","optimization","intervention","monitoring","event","object","declarative","procedural"})


@dataclass(frozen=True)
class MethodCoverage:
    present: frozenset[str]

    @property
    def missing(self) -> frozenset[str]:
        return REQUIRED - self.present

    @property
    def complete(self) -> bool:
        return not self.missing
