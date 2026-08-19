"""Real, Chicago-style round trip: `GymAct.act()` -> real `AuthorityResolver`
+ real `CapabilityScope` gates -> `PlatformConsoleProvider` -> a real HTTP
call to a real platform-console deployment, authenticated with a real
service-account `Authorization: Bearer pk_live_...` key.

No `unittest.mock`/`monkeypatch` of the HTTP layer, `AuthorityResolver`, or
`CapabilityScope` anywhere in this file. When no reachable test-tenant
platform-console deployment + real minted API key are configured, the
round-trip test is skipped (named + reported), never faked -- per
`docs/DOD-v26.8.18-FDE-ACTUATION.md` §4's own explicit allowance.

Required environment for the live round trip:
  - `PLATFORM_CONSOLE_BASE_URL`: e.g. `http://localhost:3000`.
  - `PLATFORM_CONSOLE_API_KEY`: a real `pk_live_...` key minted via a real
    owner session calling `POST /api/api-keys` against that same
    deployment.
"""

from __future__ import annotations

import os

import pytest

from gymact.agent import AllowListCapabilityScope
from gymact.authority import AllowListAuthorityResolver
from gymact.gyms.platform_console_provider import PLATFORM_CONSOLE_CAPABILITIES, PlatformConsoleProvider
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, MaterializationIntent

BASE_URL = os.environ.get("PLATFORM_CONSOLE_BASE_URL")
API_KEY = os.environ.get("PLATFORM_CONSOLE_API_KEY")

_RUN_CAPABILITY = PLATFORM_CONSOLE_CAPABILITIES[0]
assert _RUN_CAPABILITY.binding == "run_inventory_components"

_live_reachable = bool(BASE_URL and API_KEY)


@pytest.mark.skipif(
    not _live_reachable,
    reason=(
        "PLATFORM_CONSOLE_BASE_URL/PLATFORM_CONSOLE_API_KEY not set -- no reachable "
        "test-tenant platform-console deployment configured. Skipped, not mocked, "
        "per docs/DOD-v26.8.18-FDE-ACTUATION.md section 4."
    ),
)
def test_real_gymact_actuates_platform_console_inventory_components() -> None:
    import anyio

    async def run() -> None:
        authority_ref = "urn:gymact:authority-decision:platform-console-e2e"
        principal = "urn:prov:agent:gymact-dod-v26.8.18"

        gym = GymAct(
            authority_resolver=AllowListAuthorityResolver({authority_ref}),
            capability_scope=AllowListCapabilityScope(
                {principal: frozenset(item.iri for item in PLATFORM_CONSOLE_CAPABILITIES)}
            ),
        )
        gym.register_provider(PlatformConsoleProvider())

        materialization = await gym.materialize(
            MaterializationIntent(
                provider="platform-console",
                config={"base_url": BASE_URL},
                principal=principal,
            )
        )
        assert materialization.accepted, materialization.receipt.reason
        episode_id = materialization.episode.episode_id

        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=_RUN_CAPABILITY.iri,
                authority_ref=authority_ref,
                principal=principal,
            )
        )
        assert result.accepted, result.receipt.reason
        assert result.effect is not None
        assert result.effect["status"] == 201
        assert result.effect["job_name"]

        verification = await gym.verify(episode_id, {})
        assert verification.passed, verification.observed

        assert gym.verify_evidence_chain()
        receipts = gym.episode_receipts(episode_id)
        assert any(r.operation.value == "act" and r.standing.value == "ALIVE" for r in receipts)

        await gym.teardown(episode_id, authority_ref=authority_ref)

    anyio.run(run)


def test_provider_refuses_without_credential() -> None:
    """Real refusal path, no live console required: a materialize attempt
    with no `PLATFORM_CONSOLE_API_KEY` and no `config.api_key` raises the
    real `PlatformConsoleAuthError`, never silently proceeding with an
    empty/placeholder credential."""
    import anyio

    from gymact.gyms.platform_console_provider import PlatformConsoleAuthError

    async def run() -> None:
        env = os.environ.pop("PLATFORM_CONSOLE_API_KEY", None)
        try:
            provider = PlatformConsoleProvider()
            with pytest.raises(PlatformConsoleAuthError):
                await provider.materialize(
                    scenario=None, config={"base_url": "http://127.0.0.1:1"}
                )
        finally:
            if env is not None:
                os.environ["PLATFORM_CONSOLE_API_KEY"] = env

    anyio.run(run)


def test_capability_scope_refuses_out_of_scope_principal() -> None:
    """Real `CapabilityScope` gate exercise, no live console required:
    `GymAct.act()` refuses the run capability for a principal not granted
    it, via a real `AllowListCapabilityScope` -- never reaching the HTTP
    layer at all (the environment here is `MemoryEnvironment`, proving the
    scope check happens before any provider-specific transport)."""
    import anyio

    from gymact.providers import MemoryProvider

    async def run() -> None:
        gym = GymAct(
            capability_scope=AllowListCapabilityScope({"urn:prov:agent:someone-else": frozenset()})
        )
        gym.register_provider(MemoryProvider())
        materialization = await gym.materialize(
            MaterializationIntent(provider="memory", config={"requires_authority": False})
        )
        assert materialization.accepted
        episode_id = materialization.episode.episode_id

        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability="urn:gymact:memory:capability:set",
                payload={"key": "x", "value": 1},
                principal="urn:prov:agent:unauthorized-caller",
            )
        )
        assert not result.accepted
        assert result.receipt.reason == "CAPABILITY_NOT_IN_SCOPE"

    anyio.run(run)
