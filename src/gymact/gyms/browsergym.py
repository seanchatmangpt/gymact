"""Real GymAct bridge to BrowserGym's local ``openended`` Chromium task.

The ForwardBench corpus pins ServiceNow/BrowserGym at
``9e779f087de9a65668b6974d11f9ce9816026e96``. At that revision,
``browsergym-core`` is version 0.14.3 and exposes the Gymnasium
``browsergym/openended`` environment plus concrete high-level navigation
procedures ``goto``, ``go_back``, and ``go_forward``.

This adapter intentionally uses only local ``about:`` task worlds in its
reference tests. It therefore exercises the real BrowserGym package and a
real Chromium process without claiming network, cloud, or Docker standing.
Checkpoint/restore is deliberately bounded to the active URL: BrowserGym does
not expose a general browser snapshot primitive, so GymAct does not pretend to
snapshot cookies, storage, history, or arbitrary page process state.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

try:
    import browsergym.core  # noqa: F401  # registers browsergym/openended
    import gymnasium as gym
except ImportError as exc:  # pragma: no cover - fail-real standing is exercised in tests
    raise ImportError(
        "browsergym bridge requires browsergym-core==0.14.3 and gymnasium; "
        "install the real BrowserGym collaborator before using this provider"
    ) from exc

BROWSERGYM_CAPABILITIES = (
    Capability(
        iri="urn:gymact:browsergym:capability:goto",
        title="Navigate the active BrowserGym page to a URL using BrowserGym goto",
        consequence=Consequence.DO,
        binding="goto",
    ),
    Capability(
        iri="urn:gymact:browsergym:capability:go-back",
        title="Navigate the active BrowserGym page backward using BrowserGym go_back",
        consequence=Consequence.DO,
        binding="go_back",
    ),
    Capability(
        iri="urn:gymact:browsergym:capability:go-forward",
        title="Navigate the active BrowserGym page forward using BrowserGym go_forward",
        consequence=Consequence.DO,
        binding="go_forward",
    ),
)


class BrowserGymEnvironment:
    """One real ``browsergym/openended`` episode backed by Chromium."""

    def __init__(self, *, start_url: str, seed: int = 0) -> None:
        self.environment_id = f"urn:gymact:browsergym:environment:{uuid4().hex}"
        self.requires_authority = True
        self._env = gym.make(
            "browsergym/openended",
            task_kwargs={"start_url": start_url, "goal": "Exercise bounded local navigation"},
            headless=True,
            wait_for_user_message=False,
            slow_mo=0,
            pre_observation_delay=0.0,
        )
        observation, _info = self._env.reset(seed=seed)
        self._observation = observation
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return BROWSERGYM_CAPABILITIES

    def _state(self) -> dict[str, Any]:
        observation = self._observation
        active_index = observation["active_page_index"]
        active_page_index = int(active_index.item() if hasattr(active_index, "item") else active_index)
        titles = list(observation["open_pages_titles"])
        return {
            "url": str(observation["url"]),
            "title": str(titles[active_page_index]) if titles else "",
            "open_page_count": len(observation["open_pages_urls"]),
            "last_action": str(observation["last_action"]),
            "last_action_error": str(observation["last_action_error"]),
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    def _action_source(self, binding: str, payload: dict[str, Any]) -> str:
        if binding == "goto":
            url = payload.get("url")
            if not isinstance(url, str) or not url:
                raise TypeError("goto requires payload.url as a non-empty string")
            return f"goto({url!r})"
        if binding == "go_back":
            return "go_back()"
        if binding == "go_forward":
            return "go_forward()"
        raise ValueError(f"unsupported BrowserGym binding: {binding}")

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = self._state()
        action = self._action_source(capability.binding, payload)
        observation, reward, terminated, truncated, _info = self._env.step(action)
        self._observation = observation
        after = self._state()
        if after["last_action_error"]:
            raise RuntimeError(f"BrowserGym action failed: {after['last_action_error']}")
        return {
            "before": before,
            "after": after,
            "action": action,
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._state()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"url": self._state()["url"]}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        url = checkpoint.get("url")
        if not isinstance(url, str) or not url:
            raise TypeError("BrowserGym checkpoint.url must be a non-empty string")
        observation, _reward, _terminated, _truncated, _info = self._env.step(f"goto({url!r})")
        self._observation = observation
        if self._state()["last_action_error"]:
            raise RuntimeError(f"BrowserGym restore failed: {self._state()['last_action_error']}")

    async def teardown(self) -> None:
        if not self._closed:
            self._env.close()
        self._closed = True


class BrowserGymProvider:
    """Materialize real local BrowserGym open-ended Chromium episodes."""

    name = "browsergym"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> BrowserGymEnvironment:
        if scenario not in (None, "openended"):
            raise ValueError("BrowserGymProvider currently supports only scenario='openended'")
        start_url = config.get("start_url", "about:blank")
        if not isinstance(start_url, str) or not start_url:
            raise TypeError("config.start_url must be a non-empty string")
        seed = config.get("seed", 0)
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError("config.seed must be an int")
        return BrowserGymEnvironment(start_url=start_url, seed=seed)
