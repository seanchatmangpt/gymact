from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceNode
from .methodology import Methodology, closed
from .receipt import Receipt
from .standing import Standing, compose_standing
from .subject import Subject


@dataclass(frozen=True, slots=True)
class Qualification:
    subject: Subject
    evidence: tuple[EvidenceNode, ...]
    methodologies: frozenset[Methodology]
    component_standing: tuple[Standing, ...]
    selector: str

    def evaluate(self) -> tuple[Standing, Receipt | None]:
        standing = compose_standing(self.component_standing)
        if not closed(self.methodologies) and standing is Standing.ALIVE:
            standing = Standing.PARTIAL_ALIVE
        if standing is Standing.BUILD_BROKEN:
            return standing, None
        receipt = Receipt(
            subject=self.subject,
            standing=standing,
            evidence_ids=tuple(node.evidence_id for node in self.evidence),
            selector=self.selector,
        )
        return standing, receipt
