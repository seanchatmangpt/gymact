from dataclasses import dataclass

from .authority import ActionClass, require
from .belief import BeliefState
from .budget import Budget
from .policy import Policy
from .receipt import AcquisitionReceipt
from .selector import select
from .sensor import SensorCapability
from .strategy import CandidateScore


@dataclass(frozen=True)
class Plan:
    selected_sensor: str
    remaining_budget: Budget
    receipt: AcquisitionReceipt


def construct_plan(
    *,
    subject: str,
    belief: BeliefState,
    policy: Policy,
    candidates: tuple[SensorCapability, ...],
    scores: dict[str, CandidateScore],
    budget: Budget,
    step: int,
) -> Plan:
    require(ActionClass.CONSTRUCT)
    choice = select(candidates, scores, budget, policy.strategy)
    remaining = budget.consume(cost=choice.sensor.cost, latency_ms=choice.sensor.latency_ms)
    standing = "PARTIAL_ALIVE" if max(belief.probabilities) > 0 else "UNKNOWN"
    receipt = AcquisitionReceipt(subject, policy.name, choice.sensor.digest, standing, step)
    return Plan(choice.sensor.digest, remaining, receipt)
