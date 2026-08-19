"""Shared-world actor views for dependency-world gyms.

A GymAct episode still has one actor-scoped Environment and therefore one
capability/observation surface. This provider adds a provider-owned world
identity so multiple episodes (Red, Blue, Gray, Observer, or other profiles)
can act on and observe the *same* bounded state without widening any actor's
capabilities.

The shared state never performs authority admission. GymAct's kernel remains
the DO boundary for each episode; this module only coordinates the synthetic
world state after the kernel admits an actuation.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from typing import Any
from uuid import uuid4

from gymact.gyms.dependency_world import (
    DependencyWorldEnvironment,
    DependencyWorldProvider,
)
from gymact.models import Capability


@dataclass(slots=True)
class _SharedState:
    world_id: str
    direct: dict[str, str]
    effective: dict[str, str]
    step: int
    history: list[dict[str, str]]
    lock: RLock
    views: int = 0


class SharedDependencyWorldEnvironment:
    """Actor-scoped Environment view over a provider-owned shared world."""

    def __init__(
        self,
        *,
        inner: DependencyWorldEnvironment,
        shared: _SharedState,
        release_world,
    ) -> None:
        self._inner = inner
        self._shared = shared
        self._release_world = release_world
        self._closed = False
        self.world_id = shared.world_id
        # world_id is correlation state, not an authority or IRI namespace.
        self.environment_id = inner.environment_id
        self.requires_authority = inner.requires_authority

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    async def _load(self) -> None:
        """Load shared state through the Environment recovery contract."""
        await self._inner.restore(
            {
                "actor": self._inner.actor,
                "step": self._shared.step,
                "direct": deepcopy(self._shared.direct),
                "effective": deepcopy(self._shared.effective),
                "history": deepcopy(self._shared.history),
            }
        )

    async def _save(self) -> None:
        """Persist actor-view state through the Environment checkpoint contract."""
        checkpoint = await self._inner.checkpoint()
        self._shared.direct = deepcopy(checkpoint["direct"])
        self._shared.effective = deepcopy(checkpoint["effective"])
        self._shared.step = int(checkpoint["step"])
        self._shared.history = deepcopy(checkpoint["history"])

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return self._inner.capabilities()

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        with self._shared.lock:
            await self._load()
            observed = await self._inner.observe()
            observed["world_id"] = self.world_id
            return observed

    async def actuate(
        self, capability: Capability, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._ensure_open()
        with self._shared.lock:
            await self._load()
            effect = await self._inner.actuate(capability, payload)
            await self._save()
            effect["world_id"] = self.world_id
            return effect

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        expected_assets = expected.get("assets", {})
        if not isinstance(expected_assets, dict):
            raise TypeError("expected.assets must be an object")
        allowed = {
            "assets",
            "world_id",
            "world_step",
            "observed_step",
            "staleness_steps",
            "actor",
        }
        unknown = set(expected) - allowed
        if unknown:
            raise ValueError(f"UNSUPPORTED_VERIFICATION:{sorted(unknown)!r}")
        passed = all(
            observed.get(key) == value
            for key, value in expected.items()
            if key != "assets"
        )
        passed = passed and all(
            observed["assets"].get(key) == value
            for key, value in expected_assets.items()
        )
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        with self._shared.lock:
            await self._load()
            checkpoint = await self._inner.checkpoint()
            checkpoint["world_id"] = self.world_id
            return checkpoint

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if checkpoint.get("world_id") != self.world_id:
            raise ValueError("CHECKPOINT_WORLD_MISMATCH")
        if checkpoint.get("actor") != self._inner.actor:
            raise ValueError("CHECKPOINT_ACTOR_MISMATCH")
        candidate = dict(checkpoint)
        candidate.pop("world_id", None)
        with self._shared.lock:
            await self._load()
            await self._inner.restore(candidate)
            await self._save()

    async def teardown(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._inner.teardown()
        finally:
            self._release_world(self.world_id)


class SharedDependencyWorldProvider(DependencyWorldProvider):
    """Dependency provider whose explicit `world_id` joins actor episodes."""

    def __init__(self, *, name, pack_dir, local_prefix) -> None:
        super().__init__(name=name, pack_dir=pack_dir, local_prefix=local_prefix)
        self._shared_worlds: dict[str, _SharedState] = {}
        self._shared_lock = RLock()

    def _acquire(self, world_id: str, seed: dict[str, Any]) -> _SharedState:
        with self._shared_lock:
            shared = self._shared_worlds.get(world_id)
            if shared is None:
                shared = _SharedState(
                    world_id=world_id,
                    direct=deepcopy(seed["direct"]),
                    effective=deepcopy(seed["effective"]),
                    step=int(seed["step"]),
                    history=deepcopy(seed["history"]),
                    lock=RLock(),
                )
                self._shared_worlds[world_id] = shared
            shared.views += 1
            return shared

    def _release(self, world_id: str) -> None:
        with self._shared_lock:
            shared = self._shared_worlds.get(world_id)
            if shared is None:
                return
            shared.views -= 1
            if shared.views <= 0:
                self._shared_worlds.pop(world_id, None)

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> SharedDependencyWorldEnvironment:
        world_id = config.get("world_id")
        if world_id is None:
            world_id = uuid4().hex
        if not isinstance(world_id, str) or not world_id.strip():
            raise TypeError("config.world_id must be a non-empty string")
        if len(world_id) > 128:
            raise ValueError("config.world_id exceeds 128 characters")

        inner_config = dict(config)
        inner_config.pop("world_id", None)
        inner = await super().materialize(scenario=scenario, config=inner_config)
        seed = await inner.checkpoint()
        shared = self._acquire(world_id, seed)
        try:
            return SharedDependencyWorldEnvironment(
                inner=inner,
                shared=shared,
                release_world=self._release,
            )
        except Exception:
            self._release(world_id)
            await inner.teardown()
            raise
