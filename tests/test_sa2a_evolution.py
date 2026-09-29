from gymact.consequence_binding import ConsequenceBinding
from gymact.sa2a_envelope import SA2A_REPLAN_CONTRACT_DIGEST
from gymact.sa2a_evolution import evolution_feedback


def test_evolution_feedback_is_deterministic_and_powerless():
    envelope = {
        "schema": "sa2a/replan-envelope/v1",
        "contract_digest": SA2A_REPLAN_CONTRACT_DIGEST,
        "exact_subject": "urn:subject:1",
        "receipt_id": "r1",
        "consequence": "failed",
        "decision": {"kind": "replan", "reason": "failed", "authority": "none"},
        "provider": "gymact",
        "projection_digest": None,
        "source_replay_key": "rk1",
    }
    binding = ConsequenceBinding(
        action_ref="urn:action:1",
        subject_ref="urn:subject:1",
        capability_ref="urn:capability:1",
        verifier_ref="urn:verifier:1",
        expected_effect_digest="sha256:" + "1" * 64,
    )

    left = evolution_feedback(envelope, binding=binding)
    right = evolution_feedback(envelope, binding=binding)

    assert left == right
    assert left.envelope_digest.startswith("blake3:")
    assert left.decision_kind == "replan"
    assert left.authority == "none"
