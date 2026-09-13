from dataclasses import dataclass


@dataclass(frozen=True)
class OcelWitness:
    semantic_digest: str
    event_digest: str
    object_digest: str


def admit_ocel(witness: OcelWitness) -> None:
    if not all((witness.semantic_digest, witness.event_digest, witness.object_digest)):
        raise ValueError("METHOD_MISMATCH")
