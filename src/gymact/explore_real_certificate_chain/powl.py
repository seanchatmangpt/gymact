from dataclasses import dataclass


@dataclass(frozen=True)
class PowlWitness:
    semantic_digest: str
    trace_digest: str
    bounded: bool
    cyclic: bool


def admit_powl(witness: PowlWitness) -> None:
    if not witness.semantic_digest or not witness.trace_digest or not witness.bounded:
        raise ValueError("METHOD_MISMATCH")
