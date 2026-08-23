from dataclasses import dataclass
from fractions import Fraction

from .authority import ActionClass, require_action
from .calibration import GainCalibration
from .policies import FeedbackPolicy, policy_score
from .receipt import FeedbackReceipt
from .subject import Subject


@dataclass(frozen=True)
class FeedbackPlan:
    policy: FeedbackPolicy
    score: Fraction
    standing: str


def construct_feedback_plan(
    subject: Subject,
    calibration: GainCalibration,
    drift: bool,
    regret: Fraction,
    policy: FeedbackPolicy,
) -> tuple[FeedbackPlan, FeedbackReceipt]:
    require_action(ActionClass.CONSTRUCT)
    standing = "REQUALIFYING" if drift or not calibration.calibrated else "PARTIAL_ALIVE"
    plan = FeedbackPlan(policy, policy_score(policy, calibration, drift, regret), standing)
    receipt = FeedbackReceipt(
        f"{subject.repo}@{subject.sha}", policy.value, standing, False
    )
    return plan, receipt
