from .primal import PrimalResult
from .dual import DualResult
from .oracle import OracleResult


def three_way_agreement(primal: PrimalResult, dual: DualResult, oracle: OracleResult) -> None:
    subjects = {primal.subject, dual.subject, oracle.subject}
    if len(subjects) != 1:
        raise ValueError("SUBJECT_DRIFT")
    if not (primal.value == dual.value == oracle.value):
        raise ValueError("ORACLE_DIVERGENCE")
