from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact.action_contract import ObservationConfidence
from gymact.evidence import digest
from gymact.models import Observation
from gymact.observation_evidence import (
    ObservationClaimRefused,
    ObservationPlane,
    ObservationWitness,
)


def _observation() -> Observation:
    state = {"status": "ready"}
    return Observation(
        episode_id="episode-1",
        state=state,
        state_digest=digest(state),
    )


@pytest.mark.parametrize(
    "plane",
    [
        ObservationPlane.UNSPECIFIED,
        ObservationPlane.SIMULATED,
        ObservationPlane.PROVIDER_REOBSERVED,
    ],
)
def test_non_external_planes_cannot_crown_external_reality(plane: ObservationPlane) -> None:
    witness = ObservationWitness.from_observation(_observation(), plane=plane)

    assert witness.admits_external_claim() is False
    with pytest.raises(ObservationClaimRefused, match="EXTERNAL_OBSERVATION_REQUIRED"):
        witness.require_external_claim()


def test_provider_observation_cannot_self_declare_independence() -> None:
    with pytest.raises(
        ValidationError,
        match="PROVIDER_OBSERVATION_CANNOT_SELF_DECLARE_INDEPENDENCE",
    ):
        ObservationWitness.from_observation(
            _observation(),
            plane=ObservationPlane.PROVIDER_REOBSERVED,
            independent=True,
        )


@pytest.mark.parametrize(
    "plane",
    [ObservationPlane.EXTERNAL_REOBSERVED, ObservationPlane.PHYSICAL_SENSOR],
)
def test_external_planes_require_explicit_independent_source(
    plane: ObservationPlane,
) -> None:
    with pytest.raises(ValidationError, match="EXTERNAL_OBSERVATION_SOURCE_REQUIRED"):
        ObservationWitness.from_observation(
            _observation(),
            plane=plane,
            independent=True,
        )

    with pytest.raises(
        ValidationError,
        match="EXTERNAL_OBSERVATION_INDEPENDENCE_REQUIRED",
    ):
        ObservationWitness.from_observation(
            _observation(),
            plane=plane,
            source_ref="urn:test:observer",
        )


def test_external_reobservation_admits_external_claim_and_confidence() -> None:
    witness = ObservationWitness.from_observation(
        _observation(),
        plane=ObservationPlane.EXTERNAL_REOBSERVED,
        source_ref="urn:test:independent-observer",
        independent=True,
    )

    assert witness.require_external_claim() is witness
    assert witness.confidence is ObservationConfidence.INDEPENDENT_CHANNEL
    assert witness.satisfies(ObservationConfidence.INDEPENDENT_CHANNEL)
    assert not witness.satisfies(ObservationConfidence.PHYSICAL_SENSOR)


def test_multiple_external_oracles_raise_confidence_without_changing_world_state() -> None:
    observation = _observation()
    witness = ObservationWitness.from_observation(
        observation,
        plane=ObservationPlane.EXTERNAL_REOBSERVED,
        source_ref="urn:test:observer:a",
        independent=True,
        oracle_refs=("urn:test:observer:a", "urn:test:observer:b"),
    )

    assert witness.observation == observation
    assert witness.confidence is ObservationConfidence.MULTI_ORACLE


def test_witness_digest_binds_plane_source_and_independence() -> None:
    observation = _observation()
    simulated = ObservationWitness.from_observation(
        observation,
        plane=ObservationPlane.SIMULATED,
    )
    external = ObservationWitness.from_observation(
        observation,
        plane=ObservationPlane.EXTERNAL_REOBSERVED,
        source_ref="urn:test:observer",
        independent=True,
    )

    assert simulated.observation.state_digest == external.observation.state_digest
    assert simulated.witness_digest != external.witness_digest

    payload = external.model_dump(mode="json")
    payload["witness_digest"] = "0" * 64
    with pytest.raises(ValidationError, match="OBSERVATION_WITNESS_DIGEST_MISMATCH"):
        ObservationWitness.model_validate(payload)
