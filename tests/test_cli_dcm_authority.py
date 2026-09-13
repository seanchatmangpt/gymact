from __future__ import annotations

import pytest

from gymact.authority import AllowListAuthorityResolver, DenyAuthorityResolver
from gymact.cli import _materialize_request
from gymact.models import Standing


@pytest.mark.asyncio
async def test_request_authority_reference_cannot_install_an_authority_resolver() -> None:
    runtime, result = await _materialize_request(
        {
            "provider": "memory",
            "config": {"initial": {"x": 1}, "requires_authority": True},
            "materialization_authority_ref": "urn:authority:request-only",
            "grant": {"authority_ref": "urn:authority:request-only"},
            "materialization_idempotency_key": "request-cannot-self-authorize",
        }
    )
    assert result.standing is Standing.ALIVE
    assert isinstance(runtime._authority, DenyAuthorityResolver)
    assert runtime.discover() == ("memory",)


@pytest.mark.asyncio
async def test_separate_operator_authority_source_installs_allow_list_resolver() -> None:
    runtime, result = await _materialize_request(
        {
            "provider": "memory",
            "config": {"initial": {"x": 1}, "requires_authority": True},
            "materialization_authority_ref": "urn:authority:operator",
            "materialization_idempotency_key": "operator-authority",
        },
        authority_refs={"urn:authority:operator"},
    )
    assert result.standing is Standing.ALIVE
    assert isinstance(runtime._authority, AllowListAuthorityResolver)
