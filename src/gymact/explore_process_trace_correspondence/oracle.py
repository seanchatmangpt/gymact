from __future__ import annotations

from dataclasses import dataclass

from .refusal import Refused
from .trace import Trace


@dataclass(frozen=True)
class OracleWitness:
    implementation: str
    trace: Trace


def require_independent(witnesses: tuple[OracleWitness, ...]) -> None:
    implementations = {w.implementation for w in witnesses}
    if len(implementations) < 2:
        raise Refused("NONINDEPENDENT_ORACLE_SET")
    subjects = {w.trace.subject for w in witnesses}
    if len(subjects) != 1:
        raise Refused("ORACLE_SUBJECT_DRIFT")
