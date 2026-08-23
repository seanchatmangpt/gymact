from fractions import Fraction
from .belief import BeliefState
from .evidence import ObservationEvidence


def update_belief(prior: BeliefState, evidence: ObservationEvidence) -> BeliefState:
    if len(prior.probabilities) != len(evidence.likelihoods):
        raise ValueError("REFUSED_LIKELIHOOD_DIMENSION")
    weights = tuple(p * l for p, l in zip(prior.probabilities, evidence.likelihoods, strict=True))
    total = sum(weights)
    if total == 0:
        raise ValueError("REFUSED_ZERO_EVIDENCE_MASS")
    posterior = tuple(Fraction(w, total) for w in weights)
    return BeliefState(prior.hypotheses, posterior)
