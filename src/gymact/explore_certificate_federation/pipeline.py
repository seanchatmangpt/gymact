from dataclasses import dataclass
from fractions import Fraction

from .certificate import Certificate
from .correspondence import RuntimeWitness, admit_correspondence
from .currentness import current_frontier
from .independence import ValidatorIdentity, require_independent
from .quorum import require_effective_quorum
from .receipt import Receipt


@dataclass(frozen=True)
class VerificationResult:
    current: tuple[Certificate, ...]
    receipt: Receipt


def verify_federation(
    certificates: tuple[Certificate, ...],
    runtime_pair: tuple[RuntimeWitness, RuntimeWitness],
    validators: tuple[ValidatorIdentity, ...],
    correlation: Fraction,
    minimum_effective: Fraction,
) -> VerificationResult:
    current = current_frontier(certificates)
    require_independent(validators, 2)
    require_effective_quorum(len(validators), correlation, minimum_effective)
    admit_correspondence(*runtime_pair)
    receipt = Receipt(current[0].subject, tuple(c.identity for c in current))
    return VerificationResult(current=current, receipt=receipt)
