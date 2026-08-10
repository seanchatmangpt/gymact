"""Real GymAct `Environment`/`EnvironmentProvider` backed by CUBE's own
`counter-cube` reference benchmark (no Docker/container dependency).

This is the first end-to-end bridge from GymAct's kernel to a real, external,
already-published benchmark package -- proving the abstraction actually
mediates a real gym's episode loop (reset/step/evaluate/close), not only
GymAct's own synthetic `MemoryEnvironment`.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

try:
    from counter_cube.task import CounterTaskConfig, CounterTaskMetadata, ReachTargetTask
    from counter_cube.tool import CounterToolConfig
except ImportError as exc:  # pragma: no cover - exercised via named skip in tests
    raise ImportError(
        "cube_counter requires the optional 'cube' extra "
        "(`uv sync --extra cube` or `--all-extras`), which installs "
        "cube-standard and counter-cube from "
        "~/autofde-lab/vendor/gyms/cube-standard"
    ) from exc

CUBE_COUNTER_CAPABILITIES = (
    Capability(
        iri="urn:gymact:cube-counter:capability:increment",
        title="Increment the CUBE counter task's counter by 1",
        consequence=Consequence.DO,
        binding="increment",
    ),
    Capability(
        iri="urn:gymact:cube-counter:capability:decrement",
        title="Decrement the CUBE counter task's counter by 1",
        consequence=Consequence.DO,
        binding="decrement",
    ),
    Capability(
        iri="urn:gymact:cube-counter:capability:increment_by",
        title="Increment the CUBE counter task's counter by an amount",
        consequence=Consequence.DO,
        binding="increment_by",
    ),
    Capability(
        iri="urn:gymact:cube-counter:capability:get_value",
        title="Read the CUBE counter task's current counter value",
        consequence=Consequence.READ,
        binding="get_value",
    ),
)


class CubeCounterEnvironment:
    """Wraps a real, freshly-`reset()` `counter_cube.task.ReachTargetTask`.

    State reads/writes go through the task's real tool (`task.tool.increment()`
    etc.) and the task's own `_env.counter` -- CUBE's real internal state, not
    a re-derived shadow copy.
    """

    def __init__(self, *, target: int, requires_authority: bool = False) -> None:
        self.environment_id = f"urn:gymact:cube-counter:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._task: ReachTargetTask = CounterTaskConfig(
            metadata=CounterTaskMetadata(id=f"counter-{uuid4().hex}", target=target),
            tool_config=CounterToolConfig(enable_decrement=True, enable_increment_by=True),
        ).make()
        self._task.reset()
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return CUBE_COUNTER_CAPABILITIES

    def _state(self) -> dict[str, Any]:
        reward, info = self._task.evaluate()
        return {
            "counter": self._task.tool._env.counter,
            "target": self._task.target,
            "reward": reward,
            "solved": bool(info.get("solved", False)),
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = self._state()
        binding = capability.binding
        if binding == "increment":
            result_text = self._task.tool.increment()
        elif binding == "decrement":
            result_text = self._task.tool.decrement()
        elif binding == "increment_by":
            result_text = self._task.tool.increment_by(int(payload["value"]))
        elif binding == "get_value":
            result_text = self._task.tool.get_value()
        else:
            raise ValueError(f"unsupported CUBE counter binding: {binding}")
        after = self._state()
        return {"before": before, "after": after, "result_text": result_text}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._state()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"counter": self._task.tool._env.counter}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._task.tool._env.counter = int(checkpoint["counter"])

    async def teardown(self) -> None:
        if not self._closed:
            self._task.close()
        self._closed = True


class CubeCounterProvider:
    """GymAct `EnvironmentProvider` that materializes real CUBE counter tasks."""

    name = "cube-counter"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> CubeCounterEnvironment:
        del scenario
        target = config.get("target", 3)
        if not isinstance(target, int) or isinstance(target, bool):
            raise TypeError("config.target must be an int")
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return CubeCounterEnvironment(target=target, requires_authority=requires_authority)
