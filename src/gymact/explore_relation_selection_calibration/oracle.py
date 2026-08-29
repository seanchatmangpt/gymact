from __future__ import annotations

from dataclasses import dataclass

from .errors import Refused


@dataclass(frozen=True)
class OracleWitness:
    implementation_digest: str
    model_digest: str


def require_independent(oracles: tuple[OracleWitness, ...]) -> None:
    if len(oracles) < 2:
        raise Refused("INSUFFICIENT_ORACLES")
    impl = {o.implementation_digest for o in oracles}
    models = {o.model_digest for o in oracles}
    if len(impl) < 2 or len(models) < 2:
        raise Refused("ORACLE_ALIASING")
