from __future__ import annotations

from dataclasses import dataclass

from .representation import RepresentationCandidate
from .roundtrip import RoundTripWitness
from .semantic_type import SemanticType
from .subject import Refusal


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    admitted: tuple[RepresentationCandidate, ...]
    refused: tuple[tuple[str, str], ...]


def admit_candidates(
    semantic_type: SemanticType,
    candidates: tuple[RepresentationCandidate, ...],
    witnesses: tuple[RoundTripWitness, ...],
    *,
    require_lossless: bool,
) -> AdmissionResult:
    witness_by_candidate = {w.via_fingerprint: w for w in witnesses}
    admitted: list[RepresentationCandidate] = []
    refused: list[tuple[str, str]] = []
    for candidate in sorted(candidates, key=lambda c: c.fingerprint):
        if candidate.semantic_type.identity != semantic_type.identity:
            refused.append((candidate.fingerprint, "REFUSED_SEMANTIC_IDENTITY_DRIFT"))
            continue
        witness = witness_by_candidate.get(candidate.fingerprint)
        if candidate.kind.value != "RDF_TERM" and witness is None:
            refused.append((candidate.fingerprint, "REFUSED_MISSING_ROUNDTRIP_WITNESS"))
            continue
        if require_lossless and witness is not None and not witness.lossless:
            refused.append((candidate.fingerprint, "REFUSED_LOSSY_ROUNDTRIP"))
            continue
        admitted.append(candidate)
    if not admitted:
        raise Refusal("REFUSED_NO_ADMITTED_REPRESENTATION")
    return AdmissionResult(tuple(admitted), tuple(refused))
