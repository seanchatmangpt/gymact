from __future__ import annotations

from dataclasses import dataclass

from .errors import Refused
from .relation import Relation


@dataclass(frozen=True)
class MetamorphicWitness:
    relation: Relation
    stutter_idempotent: bool
    independent_commutation: bool

    def admits(self) -> bool:
        if self.relation is Relation.STUTTER:
            return self.stutter_idempotent
        if self.relation is Relation.PARTIAL_ORDER:
            return self.independent_commutation
        return True


def require_lawful(witness: MetamorphicWitness) -> None:
    if not witness.admits():
        raise Refused("METAMORPHIC_LAW_FAILED", witness.relation.value)
