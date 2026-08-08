from __future__ import annotations

import pytest

from gymact.cli import _materialize_request
from gymact.models import Standing


@pytest.mark.asyncio
async def test_request_authority_reference_does_not_authorize_materialization() -> None:
    runtime, result = await _materialize_request(
        {
            "provider": "memory",
            "config": {"initial": {"x": 1}, "requires_authority": True},
            "materialization_authority_ref": "urn:authority:request-only",
            "grant": {"authority_ref": "urn:authority:request-only"},
            "materialization_idempotency_key": "request-cannot-self-authorize",
        }
    )
    assert result.standing is Standing.REFUSED
    assert result.receipt.reason == "AUTHORITY_NOT_ADMITTED"
    assert runtime.discover() == ("memory",)


@pytest.mark.asyncio
async def test_separate_operator_authority_source_can_admit_exact_reference() -> None:
    _, result = await _materialize_request(
        {
            "provider": "memory",
            "config": {"initial": {"x": 1}, "requires_authority": True},
            "materialization_authority_ref": "urn:authority:operator",
            "materialization_idempotency_key": "operator-authority",
        },
        authority_refs={"urn:authority:operator"},
    )
    assert result.standing is Standing.ALIVE
    assert result.receipt.authority_evidence_ref is not None
