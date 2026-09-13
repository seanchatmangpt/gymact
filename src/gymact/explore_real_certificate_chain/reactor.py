from dataclasses import dataclass


@dataclass(frozen=True)
class ReactorWitness:
    semantic_digest: str
    plan_digest: str
    execution_digest: str
    receipt_digest: str


def reactor_corresponds(w: ReactorWitness) -> bool:
    return all((w.semantic_digest, w.plan_digest, w.execution_digest, w.receipt_digest))
