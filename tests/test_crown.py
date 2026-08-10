from __future__ import annotations

import pytest

from gymact.capsule import CapsuleIdentity
from gymact.crown import CrownAdmissionError, CrownEvidence, CrownReceipt, frontier_result_from_crown
from gymact.models import Standing
from gymact.sota import dominates


def _capsule() -> CapsuleIdentity:
    return CapsuleIdentity(
        source_digest="source",
        validator_digest="validator",
        toolchain_digest="toolchain",
        config_digest="config",
        environment_digest="environment",
    )


def _crown(**updates) -> CrownReceipt:  # type: ignore[no-untyped-def]
    evidence = CrownEvidence(
        subject_digest="subject",
        experiment_digest="experiment",
        admitted_observation_digest="observation",
        authority_evidence_ref="authority",
        consequence_digest="consequence",
        verifier_digest="verifier",
        receipt_digest="receipt",
        replay_receipt_digest="replay",
        observed=True,
        admitted=True,
        executed=True,
        changed=True,
        verified=True,
        replayed=True,
    ).model_copy(update=updates)
    return CrownReceipt(
        capsule=_capsule(),
        evidence=evidence,
        transition_receipt_id="transition",
        standing=Standing.ALIVE,
    )


def test_crown_requires_replay_and_verification() -> None:
    with pytest.raises(CrownAdmissionError, match="REPLAY_NOT_VERIFIED"):
        _crown(replayed=False).admit()
    with pytest.raises(CrownAdmissionError, match="CONSEQUENCE_NOT_VERIFIED"):
        _crown(verified=False).admit()


def test_crown_requires_observed_admitted_execution() -> None:
    with pytest.raises(CrownAdmissionError, match="OBSERVATION_NOT_OBSERVED"):
        _crown(observed=False).admit()
    with pytest.raises(CrownAdmissionError, match="OBSERVATION_NOT_ADMITTED"):
        _crown(admitted=False).admit()
    with pytest.raises(CrownAdmissionError, match="SUBJECT_NOT_EXECUTED"):
        _crown(executed=False).admit()


def test_non_alive_crown_cannot_enter_frontier() -> None:
    crown = _crown().model_copy(update={"standing": Standing.PARTIAL_ALIVE})
    with pytest.raises(CrownAdmissionError, match="STANDING_NOT_ALIVE"):
        frontier_result_from_crown(crown, result_id="candidate", metrics={"quality": 1.0})


def test_crown_projects_to_sota_without_losing_replay_gate() -> None:
    candidate = frontier_result_from_crown(
        _crown(), result_id="candidate", metrics={"quality": 1.0, "cost": 0.0}
    )
    challenger = frontier_result_from_crown(
        _crown(), result_id="challenger", metrics={"quality": 2.0, "cost": 0.0}
    )
    assert dominates(challenger, candidate) is True


def test_crown_digest_changes_when_evidence_changes() -> None:
    baseline = _crown()
    changed = _crown(consequence_digest="different")
    assert baseline.evidence.crown_digest != changed.evidence.crown_digest
    assert baseline.receipt_digest != changed.receipt_digest
