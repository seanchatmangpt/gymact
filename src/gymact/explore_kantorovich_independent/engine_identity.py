from __future__ import annotations

from dataclasses import dataclass

from .refusal import IndependentVerifierRefusal


@dataclass(frozen=True)
class EngineIdentity:
    semantic: str
    implementation: str
    model: str

    def independent_of(self, other: "EngineIdentity") -> bool:
        return self.implementation != other.implementation and self.model != other.model


def admit_independent(verifier: EngineIdentity, manufacturer: EngineIdentity) -> None:
    if not verifier.independent_of(manufacturer):
        raise IndependentVerifierRefusal("PSEUDO_INDEPENDENT_VERIFIER", f"{verifier.implementation}/{verifier.model}")


INDEPENDENT_ENGINE = EngineIdentity("kantorovich-duality/v1", "equation-verifier", "raw-primal-dual")
MANUFACTURER_ENGINE = EngineIdentity("kantorovich-duality/v1", "certificate-manufacturer", "composed-certify")
