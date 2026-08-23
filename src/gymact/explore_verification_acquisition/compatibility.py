from dataclasses import dataclass

from .capability import RailCapability
from .subject import Refusal, Subject


@dataclass(frozen=True, slots=True)
class PlanCompatibility:
    subject: Subject
    rail_fingerprints: tuple[str, ...]


def admit_compatible(
    subject: Subject,
    rails: tuple[RailCapability, ...],
    witness: PlanCompatibility,
) -> None:
    if witness.subject != subject:
        raise Refusal("REFUSED_FOREIGN_ACQUISITION_PLAN")
    actual = tuple(sorted(rail.fingerprint for rail in rails))
    if tuple(sorted(witness.rail_fingerprints)) != actual:
        raise Refusal("REFUSED_STALE_ACQUISITION_PLAN")
