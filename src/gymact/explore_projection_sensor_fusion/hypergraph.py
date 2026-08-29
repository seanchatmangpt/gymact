from dataclasses import dataclass

from .independence import IndependenceProof


@dataclass(frozen=True, slots=True)
class IndependenceHypergraph:
    proofs: tuple[IndependenceProof, ...]

    def neighbors(self, sensor_id: str) -> frozenset[str]:
        neighbors: set[str] = set()
        for proof in self.proofs:
            pair = proof.pair()
            if sensor_id in pair:
                neighbors.update(pair - {sensor_id})
        return frozenset(neighbors)

    def independent_clique(self, sensor_ids: frozenset[str]) -> bool:
        return all((b in self.neighbors(a)) for a in sensor_ids for b in sensor_ids if a != b)
