from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class OracleResult:
    subject: str
    value: Fraction
    witness_digest: str


def bind_oracle(subject: str, value: Fraction, witness_digest: str) -> OracleResult:
    if value < 0 or not witness_digest:
        raise ValueError("ORACLE_DIVERGENCE")
    return OracleResult(subject, value, witness_digest)
