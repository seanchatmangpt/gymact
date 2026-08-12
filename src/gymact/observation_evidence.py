"""Explicit evidence planes for GymAct observations.

The core :class:`Observation` remains backward-compatible. `ObservationWitness`
adds the evidence needed to distinguish simulated/provider-local state from an
independently re-observed external world.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from gymact.action_contract import ObservationConfidence
from gymact.evidence import digest
from gymact.models import FrozenModel, Observation


class ObservationPlane(StrEnum):
    UNSPECIFIED = "UNSPECIFIED"
    SIMULATED = "SIMULATED"
    PROVIDER_REOBSERVED = "PROVIDER_REOBSERVED"
    EXTERNAL_REOBSERVED = "EXTERNAL_REOBSERVED"
    PHYSICAL_SENSOR = "PHYSICAL_SENSOR"


class ObservationClaimRefused(RuntimeError):
    """Raised when evidence is too weak for the requested standing."""


_CONFIDENCE_RANK = {
    ObservationConfidence.SELF_REPORTED: 0,
    ObservationConfidence.SAME_PROVIDER_OBSERVED: 1,
    ObservationConfidence.INDEPENDENT_CHANNEL: 2,
    ObservationConfidence.MULTI_ORACLE: 3,
    ObservationConfidence.PHYSICAL_SENSOR: 4,
}


class ObservationWitness(FrozenModel):
    """Content-addressed provenance for one existing GymAct observation."""

    observation: Observation
    plane: ObservationPlane = ObservationPlane.UNSPECIFIED
    source_ref: str | None = None
    independent: bool = False
    oracle_refs: tuple[str, ...] = ()
    witness_digest: str = Field(min_length=1)

    @classmethod
    def from_observation(
        cls,
        observation: Observation,
        *,
        plane: ObservationPlane = ObservationPlane.UNSPECIFIED,
        source_ref: str | None = None,
        independent: bool = False,
        oracle_refs: tuple[str, ...] = (),
    ) -> "ObservationWitness":
        payload = {
            "observation": observation.model_dump(mode="json"),
            "plane": plane.value,
            "source_ref": source_ref,
            "independent": independent,
            "oracle_refs": oracle_refs,
        }
        return cls(
            observation=observation,
            plane=plane,
            source_ref=source_ref,
            independent=independent,
            oracle_refs=oracle_refs,
            witness_digest=digest(payload),
        )

    def _payload(self) -> dict[str, object]:
        return {
            "observation": self.observation.model_dump(mode="json"),
            "plane": self.plane.value,
            "source_ref": self.source_ref,
            "independent": self.independent,
            "oracle_refs": self.oracle_refs,
        }

    @model_validator(mode="after")
    def enforce_evidence_law(self) -> Self:
        if self.witness_digest != digest(self._payload()):
            raise ValueError("OBSERVATION_WITNESS_DIGEST_MISMATCH")
        if self.plane in {
            ObservationPlane.EXTERNAL_REOBSERVED,
            ObservationPlane.PHYSICAL_SENSOR,
        }:
            if not self.source_ref:
                raise ValueError("EXTERNAL_OBSERVATION_SOURCE_REQUIRED")
            if not self.independent:
                raise ValueError("EXTERNAL_OBSERVATION_INDEPENDENCE_REQUIRED")
        if self.plane is ObservationPlane.PROVIDER_REOBSERVED and self.independent:
            raise ValueError("PROVIDER_OBSERVATION_CANNOT_SELF_DECLARE_INDEPENDENCE")
        return self

    @property
    def confidence(self) -> ObservationConfidence:
        if self.plane is ObservationPlane.PHYSICAL_SENSOR:
            return ObservationConfidence.PHYSICAL_SENSOR
        if self.plane is ObservationPlane.EXTERNAL_REOBSERVED:
            if len(self.oracle_refs) >= 2:
                return ObservationConfidence.MULTI_ORACLE
            return ObservationConfidence.INDEPENDENT_CHANNEL
        if self.plane is ObservationPlane.PROVIDER_REOBSERVED:
            return ObservationConfidence.SAME_PROVIDER_OBSERVED
        return ObservationConfidence.SELF_REPORTED

    def satisfies(self, minimum: ObservationConfidence) -> bool:
        return _CONFIDENCE_RANK[self.confidence] >= _CONFIDENCE_RANK[minimum]

    def admits_external_claim(self) -> bool:
        return (
            self.plane
            in {ObservationPlane.EXTERNAL_REOBSERVED, ObservationPlane.PHYSICAL_SENSOR}
            and self.independent
            and bool(self.source_ref)
        )

    def require_external_claim(self) -> "ObservationWitness":
        if not self.admits_external_claim():
            raise ObservationClaimRefused(
                f"REFUSED:EXTERNAL_OBSERVATION_REQUIRED:{self.plane.value}"
            )
        return self
