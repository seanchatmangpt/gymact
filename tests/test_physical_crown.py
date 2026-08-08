import pytest

from gymact.models import Standing
from gymact.physical import (
    ControllerMode,
    EdgeControllerArtifact,
    PhysicalCommand,
    PhysicalDomain,
    PhysicalProviderProfile,
    RiskClass,
    SafetyEnvelope,
    admit_physical_command,
)


def envelope() -> SafetyEnvelope:
    return SafetyEnvelope(
        domain=PhysicalDomain.ROBOTICS,
        allowed_operations=("move",),
        policy_refs=("odrl:policy:1",),
        emergency_stop_ref="urn:estop:1",
        physical_verifier_ref="urn:sensor:1",
        safe_state_ref="urn:safe:home",
        max_duration_s=2.0,
        max_rate_hz=10.0,
    )


def test_physical_command_is_candidate_only_and_requires_authority() -> None:
    command = PhysicalCommand(
        domain=PhysicalDomain.ROBOTICS,
        operation="move",
        subject_ref="urn:robot:1",
        sequence=1,
        requested_duration_s=1,
        risk=RiskClass.CONSEQUENTIAL,
        expected_effect_ref="urn:effect:pose",
    )
    denied = admit_physical_command(envelope(), command)
    assert not denied.admitted
    assert denied.reason == "AUTHORITY_REFUSED"

    admitted = admit_physical_command(
        envelope(),
        command.model_copy(update={"authority_ref": "urn:authority:1"}),
    )
    assert admitted.admitted
    assert admitted.standing is Standing.CANDIDATE


def test_irreversible_physical_command_requires_human_approval() -> None:
    command = PhysicalCommand(
        domain=PhysicalDomain.ROBOTICS,
        operation="move",
        subject_ref="urn:robot:1",
        sequence=1,
        requested_duration_s=1,
        risk=RiskClass.IRREVERSIBLE,
        expected_effect_ref="urn:effect:pose",
        authority_ref="urn:authority:1",
    )
    assert admit_physical_command(envelope(), command).reason == "HUMAN_APPROVAL_REQUIRED"


def test_physical_alive_cannot_be_declared_without_real_subject_evidence() -> None:
    with pytest.raises(ValueError, match="REAL_SUBJECT_EVIDENCE"):
        PhysicalProviderProfile(
            provider_ref="urn:p",
            domain=PhysicalDomain.INDUSTRIAL_OT,
            driver_protocol="opcua",
            safety_envelope_ref="urn:s",
            standing=Standing.ALIVE,
        )


def test_edge_manifest_cannot_crown_itself_alive() -> None:
    args = {
        "controller_id": "edge-1",
        "action_refs": ("urn:a",),
        "authority_policy_refs": ("urn:p",),
        "verifier_refs": ("urn:v",),
        "safe_state_ref": "urn:safe",
        "execution_mode": ControllerMode.WASM,
        "content_digest": "deadbeef",
        "causal_site": "factory-1",
    }
    artifact = EdgeControllerArtifact(**args)
    assert artifact.standing is Standing.STRUCTURAL
    with pytest.raises(ValueError, match="EXECUTION_RECEIPT"):
        EdgeControllerArtifact(**args, standing=Standing.ALIVE)
