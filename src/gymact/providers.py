"""Environment/provider contracts and a deterministic reference gym."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4


@runtime_checkable
class Environment(Protocol):
    """Materialized bounded world exposed to GymAct."""

    environment_id: str
    requires_authority: bool

    async def observe(self) -> dict[str, Any]: ...

    async def actuate(self, affordance: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]: ...

    async def checkpoint(self) -> dict[str, Any]: ...

    async def restore(self, checkpoint: dict[str, Any]) -> None: ...

    async def teardown(self) -> None: ...


@runtime_checkable
class EnvironmentProvider(Protocol):
    """Factory for materialized environment instances."""

    name: str

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> Environment: ...


class MemoryEnvironment:
    """Deterministic executable reference world used for contract validation."""

    def __init__(
        self, *, initial: dict[str, Any] | None = None, requires_authority: bool = False
    ) -> None:
        self.environment_id = f"memory-{uuid4().hex}"
        self.requires_authority = requires_authority
        self._state: dict[str, Any] = deepcopy(initial or {})
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return deepcopy(self._state)

    async def actuate(self, affordance: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = deepcopy(self._state)
        if affordance == "set":
            key = str(payload["key"])
            self._state[key] = deepcopy(payload.get("value"))
        elif affordance == "delete":
            key = str(payload["key"])
            self._state.pop(key, None)
        elif affordance == "increment":
            key = str(payload["key"])
            amount = payload.get("amount", 1)
            current = self._state.get(key, 0)
            if not isinstance(current, (int, float)) or not isinstance(amount, (int, float)):
                raise TypeError("increment requires numeric current value and amount")
            self._state[key] = current + amount
        else:
            raise ValueError(f"unsupported affordance: {affordance}")
        return {"before": before, "after": deepcopy(self._state), "affordance": affordance}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return deepcopy(self._state)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._state = deepcopy(checkpoint)

    async def teardown(self) -> None:
        self._closed = True


class MemoryProvider:
    """Reference provider that materializes isolated in-memory worlds."""

    name = "memory"

    def __init__(self, *, requires_authority: bool = False) -> None:
        self.requires_authority = requires_authority

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> MemoryEnvironment:
        del scenario
        initial = config.get("initial", {})
        if not isinstance(initial, dict):
            raise TypeError("config.initial must be an object")
        required = bool(config.get("requires_authority", self.requires_authority))
        return MemoryEnvironment(initial=initial, requires_authority=required)
