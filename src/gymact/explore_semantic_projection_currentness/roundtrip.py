from __future__ import annotations

from dataclasses import dataclass

from .graph import ConversionGraph, ConversionPath
from .representation import RepresentationCandidate
from .subject import Refusal


@dataclass(frozen=True, slots=True)
class RoundTripWitness:
    source_fingerprint: str
    via_fingerprint: str
    forward: ConversionPath
    backward: ConversionPath

    @property
    def lossless(self) -> bool:
        return (self.forward.loss + self.backward.loss).lossless


def witness(
    graph: ConversionGraph,
    source: RepresentationCandidate,
    via: RepresentationCandidate,
    *,
    require_lossless: bool = False,
) -> RoundTripWitness:
    if source.semantic_type.identity != via.semantic_type.identity:
        raise Refusal("REFUSED_SEMANTIC_IDENTITY_DRIFT")
    result = RoundTripWitness(
        source.fingerprint,
        via.fingerprint,
        graph.shortest(source, via),
        graph.shortest(via, source),
    )
    if require_lossless and not result.lossless:
        raise Refusal("REFUSED_LOSSY_ROUNDTRIP")
    return result
