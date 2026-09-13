from dataclasses import dataclass
from .dual import DualResult
from .oracle import OracleResult
from .primal import PrimalResult
from .strong_duality import strong_duality
from .three_way import three_way_agreement


@dataclass(frozen=True)
class CertificateChain:
    subject: str
    value: object
    plan_digest: str
    potential_digest: str
    oracle_digest: str


def certify(primal: PrimalResult, dual: DualResult, oracle: OracleResult) -> CertificateChain:
    strong_duality(primal, dual)
    three_way_agreement(primal, dual, oracle)
    return CertificateChain(primal.subject, primal.value, primal.plan_digest, dual.potential_digest, oracle.witness_digest)
