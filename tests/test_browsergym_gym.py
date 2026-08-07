"""Chicago-style BrowserGym integration against a real Chromium process."""

from __future__ import annotations

import importlib.util
import shutil
from importlib import metadata
from pathlib import Path

from gymact.standing import require_standing

PINNED_BROWSERGYYM_VERSION = "0.14.3"
STANDING = "LOCAL_GYM:browsergym-openended"
START_URL = "data:text/html,<title>start</title><h1>start</h1>"
TARGET_URL = "data:text/html,<title>target</title><h1>target</h1>"
AUTHORITY = "urn:test:browsergym-authority"


def _system_chromium() -> str | None:
    for binary in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        resolved = shutil.which(binary)
        if resolved:
            return resolved
    return None


def _real_browsergym_available() -> bool:
    if importlib.util.find_spec("browsergym.core") is None:
        return False
    if importlib.util.find_spec("gymnasium") is None:
        return False
    try:
        if metadata.version("browsergym-core") != PINNED_BROWSERGYYM_VERSION:
            return False
    except metadata.PackageNotFoundError:
        return False
    if _system_chromium() is not None:
        return True
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
        "real browsergym-core==0.14.3 plus an executable Chromium is required; "
        "this standing is the no-network BrowserGym openended task, not a cloud/browser mock"
    ),
)

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.browsergym import BROWSERGYM_CAPABILITIES, BrowserGymProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.semantic import ProfileAuthority  # noqa: E402

GOTO_CAPABILITY = "urn:gymact:browsergym:capability:goto"


def _config(*, requires_authority: bool = True) -> dict[str, object]:
    config: dict[str, object] = {
        "start_url": START_URL,
        "requires_authority": requires_authority,
        "seed": 0,
    }
    chromium = _system_chromium()
    if chromium is not None:
        config["chromium_executable"] = chromium
    return config


def test_browsergym_capabilities_are_real_sosa_procedures_conforming_to_profile() -> None:
    result = ProfileAuthority().validate_capabilities(BROWSERGYM_CAPABILITIES)

    assert result.conforms is True, result.report_text
    assert result.custom_tbox_terms == ()


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

    verified = await gym.verify(episode_id, {"url": TARGET_URL, "title": "target"})
    assert verified.passed is True
    teardown = await gym.teardown(episode_id)
    assert teardown.operation == Operation.TEARDOWN
    assert teardown.standing == Standing.ALIVE


async def test_authority_refusal_does_not_change_real_browser_state() -> None:
    gym = GymAct()
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
    await gym.teardown(episode_id)


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
    await gym.teardown(episode_id)


async def test_browsergym_checkpoint_restore_is_bounded_to_active_url() -> None:
    provider = BrowserGymProvider()
    environment = await provider.materialize(scenario="openended", config=_config())
    checkpoint = await environment.checkpoint()
    goto = next(cap for cap in environment.capabilities() if cap.binding == "goto")

    await environment.actuate(goto, {"url": TARGET_URL})
    assert (await environment.observe())["url"] == TARGET_URL

    await environment.restore(checkpoint)
    restored = await environment.observe()
    assert restored["url"] == START_URL
    assert restored["title"] == "start"
    await environment.teardown()
