"""Differential multi-oracle verification over explicitly independent access paths."""
from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import Field

from gymact.action_contract import ObservationConfidence
from gymact.evidence import digest
from gymact.models import FrozenModel, Standing


class OracleObservation(FrozenModel):
    oracle_ref: str = Field(min_length=1)
    channel_ref: str = Field(min_length=1)
    state: dict[str, Any]
    state_digest: str = Field(min_length=1)
    confidence: ObservationConfidence


class DifferentialVerification(FrozenModel):
    standing: Standing
    passed: bool
    quorum: int = Field(ge=2)
    agreeing_digest: str | None = None
    oracle_refs: tuple[str, ...]
    channel_refs: tuple[str, ...]
    reason: str


def observe_oracle(
    *,
    oracle_ref: str,
    channel_ref: str,
    state: dict[str, Any],
    confidence: ObservationConfidence = ObservationConfidence.INDEPENDENT_CHANNEL,
) -> OracleObservation:
    return OracleObservation(
        oracle_ref=oracle_ref,
        channel_ref=channel_ref,
        state=state,
        state_digest=digest(state),
        confidence=confidence,
    )


def _partial_match(observed: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            key in observed and _partial_match(observed[key], value)
            for key, value in expected.items()
        )
    return observed == expected


def differential_verify(
    observations: tuple[OracleObservation, ...],
    *,
    expected: dict[str, Any],
    quorum: int = 2,
) -> DifferentialVerification:
    """Require distinct oracle and channel identities before counting quorum."""
    if quorum < 2:
        raise ValueError("DIFFERENTIAL_QUORUM_MUST_BE_AT_LEAST_TWO")
    if len(observations) < quorum:
        raise ValueError("DIFFERENTIAL_VERIFICATION_REQUIRES_QUORUM_OBSERVATIONS")
    oracle_refs = tuple(item.oracle_ref for item in observations)
    channel_refs = tuple(item.channel_ref for item in observations)
    if len(set(oracle_refs)) != len(oracle_refs):
        raise ValueError("DIFFERENTIAL_ORACLES_MUST_BE_DISTINCT")
    if len(set(channel_refs)) != len(channel_refs):
        raise ValueError("DIFFERENTIAL_CHANNELS_MUST_BE_DISTINCT")
    if any(item.state_digest != digest(item.state) for item in observations):
        raise ValueError("ORACLE_STATE_DIGEST_MISMATCH")

    counts = Counter(item.state_digest for item in observations)
    agreeing_digest, count = counts.most_common(1)[0]
    agreeing = tuple(item for item in observations if item.state_digest == agreeing_digest)
    expected_passed = count >= quorum and all(
        _partial_match(item.state, expected) for item in agreeing
    )
    return DifferentialVerification(
        standing=Standing.ALIVE if expected_passed else Standing.UNCERTAIN,
        passed=expected_passed,
        quorum=quorum,
        agreeing_digest=agreeing_digest if count >= quorum else None,
        oracle_refs=oracle_refs,
        channel_refs=channel_refs,
        reason=(
            "INDEPENDENT_ORACLE_QUORUM_VERIFIED"
            if expected_passed
            else "INDEPENDENT_ORACLE_QUORUM_NOT_ESTABLISHED"
        ),
    )
