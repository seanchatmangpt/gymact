"""Chicago-style BrowserGym boundary and failure-path coverage."""

from __future__ import annotations

import importlib.util
from importlib import metadata
from pathlib import Path

import pytest

from gymact.standing import require_standing

PINNED_BROWSERGYM_VERSION = "0.14.3"
STANDING = "LOCAL_GYM:browsergym-openended"


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

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.browsergym import BrowserGymEnvironment, BrowserGymProvider
from gymact.models import ActuationIntent, Standing

START_URL = "about:blank#start"
AUTHORITY = "urn:test:browsergym-authority"
GOTO_CAPABILITY = "urn:gymact:browsergym:capability:goto"


async def test_provider_rejects_invalid_configuration_before_browser_launch() -> None:
    provider = BrowserGymProvider()

    with pytest.raises(ValueError, match="supports only scenario"):
        await provider.materialize(scenario="webarena", config={"start_url": START_URL})
    with pytest.raises(TypeError, match="config.start_url"):
        await provider.materialize(scenario="openended", config={"start_url": ""})
    with pytest.raises(TypeError, match="config.seed"):
        await provider.materialize(
            scenario="openended", config={"start_url": START_URL, "seed": True}
        )


async def test_uninitialized_and_torn_down_environment_fail_closed() -> None:
    environment = BrowserGymEnvironment(start_url=START_URL)

    with pytest.raises(RuntimeError, match="not initialized"):
        environment.capabilities()
    await environment.teardown()
    await environment.teardown()
    with pytest.raises(RuntimeError, match="torn down"):
        await environment.observe()


async def test_real_browsergym_action_errors_are_receipted_without_navigation() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(BrowserGymProvider())
    materialized = await gym.materialize(
        MaterializationIntent(
            provider="browsergym",
            scenario="openended",
            config={"start_url": START_URL, "seed": 0},
        )
    )
    episode_id = materialized.episode.episode_id

    invalid_payload = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GOTO_CAPABILITY,
            payload={},
            authority_ref=AUTHORITY,
        )
    )
    assert invalid_payload.accepted is False
    assert invalid_payload.standing == Standing.BLOCKED
    assert invalid_payload.receipt.reason == "PROVIDER_ERROR:TypeError"
    assert invalid_payload.receipt.error_digest is not None
    assert invalid_payload.observation.state["url"] == START_URL

    invalid_url = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=GOTO_CAPABILITY,
            payload={"url": "not-a-url"},
            authority_ref=AUTHORITY,
        )
    )
    assert invalid_url.accepted is False
    assert invalid_url.standing == Standing.BLOCKED
    assert invalid_url.receipt.reason == "PROVIDER_ERROR:RuntimeError"
    assert invalid_url.receipt.error_digest is not None
    assert invalid_url.observation.state["url"] == START_URL
    assert "Cannot navigate to invalid URL" in invalid_url.observation.state["last_action_error"]

    teardown = await gym.teardown(episode_id, authority_ref=AUTHORITY)
    assert teardown.standing == Standing.ALIVE


async def test_real_browsergym_restore_errors_are_receipted_without_navigation() -> None:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(BrowserGymProvider())
    materialized = await gym.materialize(
        MaterializationIntent(
            provider="browsergym",
            scenario="openended",
            config={"start_url": START_URL, "seed": 0},
        )
    )
    episode_id = materialized.episode.episode_id

    invalid_checkpoint = await gym.restore(episode_id, {"url": ""}, authority_ref=AUTHORITY)
    assert invalid_checkpoint.standing == Standing.BLOCKED
    assert invalid_checkpoint.reason == "PROVIDER_ERROR:TypeError"
    assert invalid_checkpoint.error_digest is not None
    assert (await gym.observe(episode_id)).state["url"] == START_URL

    invalid_url = await gym.restore(
        episode_id, {"url": "not-a-url"}, authority_ref=AUTHORITY
    )
    assert invalid_url.standing == Standing.BLOCKED
    assert invalid_url.reason == "PROVIDER_ERROR:RuntimeError"
    assert invalid_url.error_digest is not None
    state = await gym.observe(episode_id)
    assert state.state["url"] == START_URL
    assert "Cannot navigate to invalid URL" in state.state["last_action_error"]

    await gym.teardown(episode_id, authority_ref=AUTHORITY)
