from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeProjection:
    runtime: str
    semantic_digest: str
    result_digest: str


def correspond(a: RuntimeProjection, b: RuntimeProjection) -> bool:
    if a.runtime == b.runtime:
        raise ValueError("NONINDEPENDENT_ENGINE")
    return a.semantic_digest == b.semantic_digest and a.result_digest == b.result_digest
