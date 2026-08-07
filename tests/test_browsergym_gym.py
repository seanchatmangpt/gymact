"""Chicago-style BrowserGym integration against a real Chromium process."""

from __future__ import annotations

import importlib.util
from importlib import metadata
from pathlib import Path

import pytest

from gymact.standing import require_standing

PINNED_BROWSERGYM_VERSION = "0.14.3"
STANDING = "LOCAL_GYM:browsergym-openended"
START_URL = "about:blank#start"
TARGET_URL = "about:blank#target"
AUTHORITY = "urn:test:browsergym-authority"


def _real_browsergym_available() -> bool:
    if importlib.util.find_spec("browsergym") is None:
        return False
    if importlib.util.find_spec("browsergym.core") is None:
        return False
    if importlib.util.find_spec("gymnasium") is None:
        return False
    try:
        if metadata.version("browsergym-core") != PINNED_BROWSERGYM_VERSION:
            return False
    except metadata.PackageNotFoundError:
        return False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).is_file()
    except Exception:
        return False


require_standing(
    STANDING,
    available=_real_browsergym_available(),
    reason=(
        "real browsergym-core==0.14.3 plus Playwright-managed Chromium is required; "
        "BrowserGym launches both task and chat browsers, so a system Chromium alone "
        "does not establish this no-network LOCAL_GYM standing"
    ),
)

from gymact import (  # noqa: E402
    AllowListAuthorityResolver,
    AuthorityDecision,
    AuthorityRequest,
    DenyAuthorityResolver,
    GymAct,
    MaterializationIntent,
)
from gymact.gyms.browsergym import BROWSERGYM_CAPABILITIES, BrowserGymProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.semantic import ProfileAuthority  # noqa: E402

GOTO_CAPABILITY = "urn:gymact:browsergym:capability:goto"
GO_BACK_CAPABILITY = "urn:gymact:browsergym:capability:go-back"
GO_FORWARD_CAPABILITY = "urn:gymact:browsergym:capability:go-forward"


class _DenyActAllowCleanupResolver:
    """Use the real deny resolver for work; separately admit bounded teardown."""

    def __init__(self) -> None:
        self._deny = DenyAuthorityResolver()

    async def authorize(self, request: AuthorityRequest) -> AuthorityDecision:
        if request.operation is Operation.TEARDOWN and request.authority_ref == AUTHORITY:
            return AuthorityDecision(
                admitted=True,
                reason="TEST_CLEANUP_ADMITTED",
                evidence_ref="urn:test:browsergym-cleanup-authority",
            )
        return await self._deny.authorize(request)


def _config() -> dict[str, object]:
    return {"start_url": START_URL, "seed": 0}


def test_browsergym_capabilities_are_real_sosa_procedures_conforming_to_profile() -> None:
    result = ProfileAuthority().validate_capabilities(BROWSERGYM_CAPABILITIES)

    assert result.conforms is True, result.report_text
    assert result.custom_tbox_terms == ()


async def test_provider_refuses_network_materialization_before_browser_launch() -> None:
    provider = BrowserGymProvider()

    with pytest.raises(ValueError, match="LOCAL_START_URL_REQUIRED"):
        await provider.materialize(
            scenario="openended",
            config={"start_url": "https://example.com", "seed": 0},
        )


async def test_real_browsergym_navigation_episode_is_receipted() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(BrowserGymProvider())
    materialized = await gym.materialize(
        MaterializationIntent(provider="browsergym", scenario="openended", config=_config())
    )
    assert materialized.accepted is True
    episode_id = materialized.episode.episode_id
    assert materialized.observation.state["url"] == START_URL

    acted = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GOTO_CAPABILITY,
            payload={"url": TARGET_URL},
            authority_ref=AUTHORITY,
        )
    )
    assert acted.accepted is True
    assert acted.receipt.operation == Operation.ACT
    assert acted.receipt.standing == Standing.ALIVE

    verified = await gym.verify(episode_id, {"url": TARGET_URL, "title": ""})
    assert verified.passed is True

    backed = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GO_BACK_CAPABILITY,
            authority_ref=AUTHORITY,
        )
    )
    assert backed.accepted is True
    assert (await gym.observe(episode_id)).state["url"] == START_URL

    forwarded = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GO_FORWARD_CAPABILITY,
            authority_ref=AUTHORITY,
        )
    )
    assert forwarded.accepted is True
    assert (await gym.observe(episode_id)).state["url"] == TARGET_URL

    teardown = await gym.teardown(episode_id, authority_ref=AUTHORITY)
    assert teardown.operation == Operation.TEARDOWN
    assert teardown.standing == Standing.ALIVE


async def test_deny_authority_resolver_does_not_change_real_browser_state() -> None:
    gym = GymAct(authority_resolver=_DenyActAllowCleanupResolver())
    gym.register_provider(BrowserGymProvider())
    materialized = await gym.materialize(
        MaterializationIntent(provider="browsergym", scenario="openended", config=_config())
    )
    assert materialized.accepted is True
    episode_id = materialized.episode.episode_id

    before = await gym.observe(episode_id)
    refused = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GOTO_CAPABILITY,
            payload={"url": TARGET_URL},
        )
    )
    after = await gym.observe(episode_id)

    assert refused.accepted is False
    assert refused.standing == Standing.REFUSED
    assert refused.receipt.reason == "LIVE_AUTHORITY_REQUIRED"
    assert before.state["url"] == START_URL
    assert after.state["url"] == START_URL
    assert refused.receipt.pre_state_digest == refused.receipt.post_state_digest

    teardown = await gym.teardown(episode_id, authority_ref=AUTHORITY)
    assert teardown.standing == Standing.ALIVE
    assert teardown.authority_evidence_ref == "urn:test:browsergym-cleanup-authority"


async def test_admitted_authority_changes_real_browser_state() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(BrowserGymProvider())
    materialized = await gym.materialize(
        MaterializationIntent(provider="browsergym", scenario="openended", config=_config())
    )
    episode_id = materialized.episode.episode_id

    refused = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GOTO_CAPABILITY,
            payload={"url": TARGET_URL},
            authority_ref="urn:test:not-admitted",
        )
    )
    assert refused.accepted is False
    assert (await gym.observe(episode_id)).state["url"] == START_URL

    admitted = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GOTO_CAPABILITY,
            payload={"url": TARGET_URL},
            authority_ref=AUTHORITY,
        )
    )
    assert admitted.accepted is True
    assert admitted.receipt.authority_evidence_ref is not None
    assert (await gym.observe(episode_id)).state["url"] == TARGET_URL
    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_browsergym_checkpoint_restore_is_bounded_to_active_url() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(BrowserGymProvider())
    materialized = await gym.materialize(
        MaterializationIntent(provider="browsergym", scenario="openended", config=_config())
    )
    episode_id = materialized.episode.episode_id
    checkpoint = await gym.checkpoint(episode_id)

    acted = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GOTO_CAPABILITY,
            payload={"url": TARGET_URL},
            authority_ref=AUTHORITY,
        )
    )
    assert acted.accepted is True
    assert (await gym.observe(episode_id)).state["url"] == TARGET_URL

    restored = await gym.restore(episode_id, checkpoint, authority_ref=AUTHORITY)
    assert restored.standing == Standing.ALIVE
    state = await gym.observe(episode_id)
    assert state.state["url"] == START_URL
    assert state.state["title"] == ""
    await gym.teardown(episode_id, authority_ref=AUTHORITY)
