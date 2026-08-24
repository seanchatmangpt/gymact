from dataclasses import dataclass
from fractions import Fraction
from .subject import Subject
from .engine_identity import EngineIdentity

@dataclass(frozen=True)
class DualCertificate:
    subject: Subject
    primal_engine: EngineIdentity
    verifier_engine: EngineIdentity
    primal_cost: Fraction
    dual_cost: Fraction
    feasible: bool
    complementary: bool

    @property
    def exact(self) -> bool:
        return self.feasible and self.complementary and self.primal_cost == self.dual_cost
