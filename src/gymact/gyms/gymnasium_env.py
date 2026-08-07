"""Real GymAct `Environment`/`EnvironmentProvider` backed by the standard,
already-installed `gymnasium` package (no vendored agentgym, no subprocess).

This is a second bridge from GymAct's kernel to a real, external,
already-published benchmark package (after `cube_counter.py`'s CUBE
integration), proving the abstraction mediates gymnasium's own real
reset/step/close episode loop against the actual `gymnasium.Env` object --
never a re-derived shadow copy of its state.

Default `env_id` is `CartPole-v1`, one of gymnasium's own bundled classic
control environments (no extra ROMs/assets, no network fetch at `make()`
time), so `materialize()` genuinely succeeds using nothing beyond the
`gyms` extra already declared in `pyproject.toml`.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import gymnasium

from gymact.models import Capability, Consequence

GYMNASIUM_CAPABILITIES = (
    Capability(
        iri="urn:gymact:gymnasium:capability:step",
        title="Step the real gymnasium environment with a legal action",
        consequence=Consequence.DO,
        binding="step",
    ),
    Capability(
        iri="urn:gymact:gymnasium:capability:reset",
        title="Reset the real gymnasium environment to a fresh episode start",
        consequence=Consequence.DO,
        binding="reset",
    ),
    Capability(
        iri="urn:gymact:gymnasium:capability:sample_action",
        title="Sample a legal random action from the real action space",
        consequence=Consequence.READ,
        binding="sample_action",
    ),
)


def _to_jsonable(value: Any) -> Any:
    """Recursively convert numpy arrays/scalars in a real gymnasium
    observation/info payload into JSON-serializable plain Python data.
    Never fabricates or drops fields -- every value is copied from the real
    object gymnasium returned."""
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


class GymnasiumEnvironment:
    """Wraps a real, freshly-`reset()` `gymnasium.Env` instance.

    All state reads/writes go through the real `gymnasium.Env` object
    (`self._env.step`, `self._env.reset`, `self._env.action_space`) -- CUBE
    counter's `_state()`/`before`/`after` pattern, applied to gymnasium's
    real `(observation, reward, terminated, truncated, info)` step tuple.
    """

    def __init__(self, *, env_id: str, requires_authority: bool = False) -> None:
        self.environment_id = f"urn:gymact:gymnasium:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._env_id = env_id
        self._env: gymnasium.Env = gymnasium.make(env_id)
        observation, info = self._env.reset()
        self._last_observation: Any = observation
        self._last_info: dict[str, Any] = info
        self._last_reward: float | None = None
        self._terminated: bool = False
        self._truncated: bool = False
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return GYMNASIUM_CAPABILITIES

    def _state(self) -> dict[str, Any]:
        return {
            "env_id": self._env_id,
            "observation": _to_jsonable(self._last_observation),
            "reward": self._last_reward,
            "terminated": self._terminated,
            "truncated": self._truncated,
            "info": _to_jsonable(self._last_info),
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = self._state()
        binding = capability.binding
        if binding == "step":
            action = payload["action"]
            if not self._env.action_space.contains(action):
                # Consequence law: request accepted != world changed. An
                # illegal action never reaches the real env.step(); refuse
                # instead of letting gymnasium raise/undefine behavior.
                raise ValueError(
                    f"action {action!r} is not legal for action_space {self._env.action_space!r}"
                )
            observation, reward, terminated, truncated, info = self._env.step(action)
            self._last_observation = observation
            self._last_reward = float(reward)
            self._terminated = bool(terminated)
            self._truncated = bool(truncated)
            self._last_info = info
        elif binding == "reset":
            observation, info = self._env.reset()
            self._last_observation = observation
            self._last_info = info
            self._last_reward = None
            self._terminated = False
            self._truncated = False
        elif binding == "sample_action":
            sampled = self._env.action_space.sample()
            after = self._state()
            return {
                "before": before,
                "after": after,
                "action": _to_jsonable(sampled),
            }
        else:
            raise ValueError(f"unsupported gymnasium binding: {binding}")
        after = self._state()
        return {"before": before, "after": after}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._state()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "observation": _to_jsonable(self._last_observation),
            "reward": self._last_reward,
            "terminated": self._terminated,
            "truncated": self._truncated,
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        # gymnasium's real Env exposes no public API to rewind internal
        # physics/RNG state to an arbitrary earlier observation -- unlike
        # CUBE counter's plain integer counter, restoring a gymnasium episode
        # to an *equivalent* internal simulator state is not something the
        # real object supports. Restoring the recorded observation/reward
        # bookkeeping is genuine (it is what `observe()`/`verify()` report),
        # but it is not a full simulator rewind; callers must not treat this
        # as resuming physics from that exact point.
        self._ensure_open()
        self._last_observation = checkpoint["observation"]
        self._last_reward = checkpoint["reward"]
        self._terminated = checkpoint["terminated"]
        self._truncated = checkpoint["truncated"]

    async def teardown(self) -> None:
        if not self._closed:
            self._env.close()
        self._closed = True


class GymnasiumProvider:
    """GymAct `EnvironmentProvider` that materializes real gymnasium environments."""

    name = "gymnasium"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> GymnasiumEnvironment:
        del scenario
        env_id = config.get("env_id", "CartPole-v1")
        if not isinstance(env_id, str):
            raise TypeError("config.env_id must be a str")
        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return GymnasiumEnvironment(env_id=env_id, requires_authority=requires_authority)
