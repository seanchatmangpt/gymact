from dataclasses import dataclass

from .refusals import Refused


@dataclass(frozen=True)
class Provenance:
    implementation: str
    model: str
    domain: str

    def independent_of(self, other: "Provenance") -> bool:
        return (
            self.implementation != other.implementation
            and self.model != other.model
            and self.domain != other.domain
        )


def require_independent(left: Provenance, right: Provenance) -> None:
    if not left.independent_of(right):
        raise Refused("UNPROVEN_INDEPENDENCE")
