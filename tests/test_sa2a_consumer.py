import pytest

from gymact.consequence_binding import ConsequenceBinding
from gymact.sa2a_consumer import consume_sa2a_replan
from gymact.sa2a_envelope import SA2A_REPLAN_CONTRACT_DIGEST


def envelope():
    return {
        "schema": "sa2a/replan-envelope/v1",
        "contract_digest": SA2A_REPLAN_CONTRACT_DIGEST,
        "exact_subject": "urn:subject:1",
        "receipt_id": "r1",
        "consequence": "unknown_outcome",
        "decision": {
            "kind": "replan",
            "reason": "unknown_outcome_reconcile_first",
            "authority": "none",
        },
        "provider": "gymact",
        "projection_digest": None,
        "source_replay_key": None,
    }


def binding(subject="urn:subject:1"):
    return ConsequenceBinding(
        action_ref="urn:action:1",
        subject_ref=subject,
        capability_ref="urn:capability:1",
        verifier_ref="urn:verifier:1",
        expected_effect_digest="sha256:" + "1" * 64,
    )


def test_consumer_preserves_upstream_recovery_decision_without_do():
    directive = consume_sa2a_replan(envelope(), binding=binding())
    assert directive.kind == "replan"
    assert directive.reason == "unknown_outcome_reconcile_first"
    assert directive.authority == "none"


def test_consumer_preserves_structured_subject_without_manufacturing_identity():
    value = envelope()
    value["exact_subject"] = {"kind": "drive", "serial": 42}
    directive = consume_sa2a_replan(value)
    assert directive.exact_subject == {"kind": "drive", "serial": 42}
    assert directive.authority == "none"


def test_consumer_refuses_subject_drift():
    with pytest.raises(ValueError, match="SA2A_EXACT_SUBJECT_MISMATCH"):
        consume_sa2a_replan(envelope(), binding=binding("urn:subject:other"))
