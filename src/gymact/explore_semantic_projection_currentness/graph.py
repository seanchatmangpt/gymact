from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush

from .converter import Converter
from .representation import RepresentationCandidate
from .subject import Refusal


@dataclass(frozen=True, slots=True)
class ConversionPath:
    converters: tuple[Converter, ...]

    @property
    def cost(self) -> int:
        return sum(edge.compute_cost for edge in self.converters)

    @property
    def loss(self):
        from .loss import LossVector
        total = LossVector()
        for edge in self.converters:
            total = total + edge.loss
        return total


class ConversionGraph:
    def __init__(self, converters: tuple[Converter, ...]) -> None:
        fingerprints = [c.fingerprint for c in converters]
        if len(fingerprints) != len(set(fingerprints)):
            raise Refusal("REFUSED_DUPLICATE_CONVERTER")
        self.converters = converters

    def shortest(self, source: RepresentationCandidate, target: RepresentationCandidate) -> ConversionPath:
        if source.fingerprint == target.fingerprint:
            return ConversionPath(())
        adjacency: dict[str, list[Converter]] = {}
        for edge in self.converters:
            adjacency.setdefault(edge.source.fingerprint, []).append(edge)
        queue: list[tuple[int, int, str, tuple[Converter, ...]]] = [(0, 0, source.fingerprint, ())]
        best: dict[str, int] = {}
        serial = 0
        while queue:
            cost, _, node, path = heappop(queue)
            if node in best and best[node] <= cost:
                continue
            best[node] = cost
            if node == target.fingerprint:
                return ConversionPath(path)
            for edge in sorted(adjacency.get(node, ()), key=lambda e: e.fingerprint):
                serial += 1
                heappush(queue, (cost + edge.compute_cost, serial, edge.target.fingerprint, path + (edge,)))
        raise Refusal("REFUSED_NO_CONVERSION_PATH")
