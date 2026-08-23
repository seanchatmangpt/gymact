from dataclasses import dataclass

from .observation import RailObservation
from .relation import EvidenceRelation, IndependenceProof, relation

@dataclass(frozen=True, slots=True)
class EvidenceCluster:
    members: tuple[RailObservation, ...]

    @property
    def outcome_set(self) -> frozenset[str]:
        return frozenset(item.outcome.value for item in self.members)

def correlated_clusters(observations: tuple[RailObservation, ...], proofs: tuple[IndependenceProof, ...] = ()) -> tuple[EvidenceCluster, ...]:
    parent = list(range(len(observations)))
    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(i: int, j: int) -> None:
        a, b = find(i), find(j)
        if a != b:
            parent[b] = a
    for i, left in enumerate(observations):
        for j in range(i + 1, len(observations)):
            if relation(left, observations[j], proofs) in {EvidenceRelation.SAME_EVIDENCE, EvidenceRelation.CORRELATED}:
                union(i, j)
    groups: dict[int, list[RailObservation]] = {}
    for i, obs in enumerate(observations):
        groups.setdefault(find(i), []).append(obs)
    return tuple(EvidenceCluster(tuple(sorted(items, key=lambda x: x.evidence_id))) for _, items in sorted(groups.items(), key=lambda kv: min(o.evidence_id for o in kv[1])))
