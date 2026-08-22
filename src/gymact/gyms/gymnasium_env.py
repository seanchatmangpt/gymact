"""Real GymAct ``Environment``/``EnvironmentProvider`` backed by Gymnasium.

The adapter keeps GymAct's consequence boundary around the real Gymnasium
``Env`` object. Checkpoints are replayable simulator checkpoints: reset seeds,
admitted step actions, and READ sampling position are recorded so ``restore``
reconstructs the real simulator state instead of only rewriting GymAct's
observation bookkeeping.
"""

from __future__ import annotations

from copy import deepcopy
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
    """Recursively convert Gymnasium/numpy values to plain Python data."""
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    return value


class GymnasiumEnvironment:
    """A real Gymnasium environment with deterministic replay checkpoints.

    Gymnasium has no generic public arbitrary-state rewind API. Rather than
    pretending that copying the last observation rewinds physics, this adapter
    records the reset seed plus every admitted step action since that reset.
    Restore resets the *real* environment with that seed, replays those actions,
    restores the action-space sampling stream, and compares the reconstructed
    state with the checkpoint. Any mismatch is refused at the provider boundary
    instead of manufacturing false rollback standing.
    """

    def __init__(
        self,
        *,
        env_id: str,
        requires_authority: bool = False,
        seed: int = 0,
    ) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("seed must be an int")
        self.environment_id = f"urn:gymact:gymnasium:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._env_id = env_id
        self._env: gymnasium.Env = gymnasium.make(env_id)
        self._seed = seed
        self._actions: list[Any] = []
        self._sample_count = 0
        observation, info = self._reset_real(self._seed)
        self._last_observation: Any = observation
        self._last_info: dict[str, Any] = info
        self._last_reward: float | None = None
        self._terminated = False
        self._truncated = False
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def _reset_real(self, seed: int) -> tuple[Any, dict[str, Any]]:
        observation, info = self._env.reset(seed=seed)
        # Sampling is READ, but deterministic sampling makes repeated bounded
        # experiments reproducible without granting any execution authority.
        self._env.action_space.seed(seed)
        return observation, info

    def _set_transition(
        self,
        observation: Any,
        reward: Any,
        terminated: Any,
        truncated: Any,
        info: dict[str, Any],
    ) -> None:
        self._last_observation = observation
        self._last_reward = float(reward)
        self._terminated = bool(terminated)
        self._truncated = bool(truncated)
        self._last_info = info

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
                raise ValueError(
                    f"action {action!r} is not legal for action_space {self._env.action_space!r}"
                )
            observation, reward, terminated, truncated, info = self._env.step(action)
            self._set_transition(observation, reward, terminated, truncated, info)
            self._actions.append(deepcopy(_to_jsonable(action)))
        elif binding == "reset":
            self._seed += 1
            observation, info = self._reset_real(self._seed)
            self._last_observation = observation
            self._last_info = info
            self._last_reward = None
            self._terminated = False
            self._truncated = False
            self._actions.clear()
            self._sample_count = 0
        elif binding == "sample_action":
            sampled = self._env.action_space.sample()
            self._sample_count += 1
            return {
                "before": before,
                "after": self._state(),
                "action": _to_jsonable(sampled),
            }
        else:
            raise ValueError(f"unsupported gymnasium binding: {binding}")
        return {"before": before, "after": self._state()}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._state()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "version": 1,
            "env_id": self._env_id,
            "seed": self._seed,
            "actions": deepcopy(self._actions),
            "sample_count": self._sample_count,
            "state": deepcopy(self._state()),
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        """Reconstruct the real simulator and falsify any replay divergence."""
        self._ensure_open()
        if checkpoint.get("version") != 1:
            raise ValueError("GYMNASIUM_CHECKPOINT_VERSION_UNSUPPORTED")
        if checkpoint.get("env_id") != self._env_id:
            raise ValueError("GYMNASIUM_CHECKPOINT_ENV_MISMATCH")
        seed = checkpoint.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("GYMNASIUM_CHECKPOINT_SEED_INVALID")
        actions = checkpoint.get("actions")
        if not isinstance(actions, list):
            raise ValueError("GYMNASIUM_CHECKPOINT_ACTIONS_INVALID")
        sample_count = checkpoint.get("sample_count")
        if (
            isinstance(sample_count, bool)
            or not isinstance(sample_count, int)
            or sample_count < 0
        ):
            raise ValueError("GYMNASIUM_CHECKPOINT_SAMPLE_COUNT_INVALID")
        expected_state = checkpoint.get("state")
        if not isinstance(expected_state, dict):
            raise ValueError("GYMNASIUM_CHECKPOINT_STATE_INVALID")
        # Validate the whole candidate before changing the real simulator.
        if any(not self._env.action_space.contains(action) for action in actions):
            raise ValueError("GYMNASIUM_CHECKPOINT_ACTION_INVALID")

        self._seed = seed
        observation, info = self._reset_real(seed)
        self._last_observation = observation
        self._last_info = info
        self._last_reward = None
        self._terminated = False
        self._truncated = False
        self._actions = []
        self._sample_count = 0

        for action in actions:
            observation, reward, terminated, truncated, info = self._env.step(action)
            self._set_transition(observation, reward, terminated, truncated, info)
            self._actions.append(deepcopy(action))
        for _ in range(sample_count):
            self._env.action_space.sample()
            self._sample_count += 1

        if self._state() != expected_state:
            raise RuntimeError("GYMNASIUM_REPLAY_RESTORE_DIVERGED")

    async def teardown(self) -> None:
        if not self._closed:
            self._env.close()
        self._closed = True


class GymnasiumProvider:
    """GymAct provider that materializes real Gymnasium environments."""

    name = "gymnasium"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> GymnasiumEnvironment:
        del scenario
        env_id = config.get("env_id", "CartPole-v1")
        if not isinstance(env_id, str):
            raise TypeError("config.env_id must be a str")
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        seed = config.get("seed", 0)
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("config.seed must be an int")
        return GymnasiumEnvironment(
            env_id=env_id,
            requires_authority=requires_authority,
            seed=seed,
        )
