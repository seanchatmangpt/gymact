from dataclasses import dataclass

from .admission import AdmissionRule, admit
from .contracts import CandidateContract
from .receipts import Receipt, digest_value
from .runtime import RuntimeCandidate


@dataclass(frozen=True)
class ExperimentOutcome:
    candidate: str
    output: dict
    receipt: Receipt


def execute(
    candidate: CandidateContract,
    runtime: RuntimeCandidate,
    payload: dict,
    rule: AdmissionRule,
) -> ExperimentOutcome:
    decision = admit(candidate, rule)
    if not decision.admitted:
        raise PermissionError(decision.reason)
    output = runtime.run(payload)
    receipt = Receipt(
        candidate.digest(),
        "CONSTRUCT",
        digest_value(payload),
        digest_value(output),
    )
    return ExperimentOutcome(candidate.name, output, receipt)
