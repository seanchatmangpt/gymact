from dataclasses import dataclass

from .refusal import Refused


@dataclass(frozen=True)
class Provenance:
    implementation: str
    model: str
    domain: str

    def require_distinct(self, other: "Provenance") -> None:
        clashes = [
            name
            for name in ("implementation", "model", "domain")
            if getattr(self, name) == getattr(other, name)
        ]
        if clashes:
            raise Refused("UNPROVEN_VALIDATOR_INDEPENDENCE", ",".join(clashes))
