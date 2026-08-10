"""Bounded, self-contained local gym: ordered hidden prerequisites behind a
chain of locks, with both reversible and irreversible actions.

Structurally distinct from `cube_counter`, `switchboard`, and `resource_flow`:

* **Ordered hidden prerequisites** -- lock `j` can only be opened while holding
  key `perm[j]`, where `perm` is a seeded permutation the environment never
  discloses. Progress is strictly sequential: lock `j+1` is untouchable until
  lock `j` is open.
* **Reversible actions** -- `pick_key` / `drop_key` move a key in and out of the
  hand and can be undone freely, so search over key choices is cheap.
* **Irreversible action + deceptive-but-lawful dead end** -- `force_latch`
  always succeeds, really advances the lock chain by one, and permanently jams
  the key rack. It therefore *looks* like progress while guaranteeing the final
  lock can never be reached whenever more than one lock remains.

Pure Python, no network, no Docker, no optional packages.
"""

from __future__ import annotations

import random
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

LOCK_AND_KEY_CAPABILITIES = (
    Capability(
        iri="urn:gymact:lock-and-key:capability:pick_key",
        title="Pick up one key from the rack (payload: {'key': int}); reversible",
        consequence=Consequence.DO,
        binding="pick_key",
    ),
    Capability(
        iri="urn:gymact:lock-and-key:capability:drop_key",
        title="Return the held key to the rack; reversible",
        consequence=Consequence.DO,
        binding="drop_key",
    ),
    Capability(
        iri="urn:gymact:lock-and-key:capability:open_lock",
        title="Open the next lock in the chain; requires the (hidden) matching held key",
        consequence=Consequence.DO,
        binding="open_lock",
    ),
    Capability(
        iri="urn:gymact:lock-and-key:capability:force_latch",
        title="Force the next lock open without a key; irreversibly jams the key rack",
        consequence=Consequence.DO,
        binding="force_latch",
    ),
    Capability(
        iri="urn:gymact:lock-and-key:capability:read_locks",
        title="Read the visible lock/rack status (never the hidden key assignment)",
        consequence=Consequence.READ,
        binding="read_locks",
    ),
)

NO_KEY = -1


class LockAndKeyEnvironment:
    """A depth-`depth` lock chain over a seeded, hidden key permutation."""

    def __init__(self, *, seed: int, depth: int, requires_authority: bool = False) -> None:
        if depth < 1:
            raise ValueError("lock-and-key requires depth >= 1")
        self.environment_id = f"urn:gymact:lock-and-key:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self.seed = seed
        self.depth = depth
        rng = random.Random(seed)
        keys = list(range(depth))
        rng.shuffle(keys)
        # Hidden: lock j is opened by key _perm[j]. Never surfaced by observe().
        self._perm: tuple[int, ...] = tuple(keys)
        self._locks_open = 0
        self._held = NO_KEY
        self._rack_jammed = False
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return LOCK_AND_KEY_CAPABILITIES

    def required_key(self) -> int:
        """Test/oracle helper: the hidden key for the next lock (-1 if solved)."""
        if self._locks_open >= self.depth:
            return NO_KEY
        return self._perm[self._locks_open]

    def _solved(self) -> bool:
        return self._locks_open >= self.depth

    def _dead_end(self) -> bool:
        if self._solved():
            return False
        if not self._rack_jammed:
            return False
        # Rack jammed: no further key can be picked up. The only way forward is
        # force_latch, which opens exactly one more lock and leaves the rest
        # unreachable; so anything past one remaining lock is unreachable, and
        # even that last one is only forceable, never openable.
        return self.depth - self._locks_open > 1

    def _state(self) -> dict[str, Any]:
        return {
            "depth": self.depth,
            "locks_open": self._locks_open,
            "held_key": self._held,
            "holding_key": self._held != NO_KEY,
            "rack_jammed": self._rack_jammed,
            "final_open": self._solved(),
            "solved": self._solved(),
            "dead_end": self._dead_end(),
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = self._state()
        binding = capability.binding
        applicable = True
        if binding == "pick_key":
            key = int(payload["key"])
            if not 0 <= key < self.depth:
                raise ValueError(f"key index out of range: {key}")
            if self._rack_jammed:
                applicable = False
                effect = "rack jammed: no key can be taken"
            elif self._held != NO_KEY:
                applicable = False
                effect = f"already holding key {self._held}"
            else:
                self._held = key
                effect = f"holding key {key}"
        elif binding == "drop_key":
            if self._held == NO_KEY:
                applicable = False
                effect = "no key held"
            else:
                dropped = self._held
                self._held = NO_KEY
                effect = f"returned key {dropped} to the rack"
        elif binding == "open_lock":
            if self._solved():
                applicable = False
                effect = "all locks already open"
            elif self._held == NO_KEY:
                applicable = False
                effect = "no key held"
            elif self._held != self._perm[self._locks_open]:
                applicable = False
                effect = "held key does not fit the next lock"
            else:
                self._locks_open += 1
                self._held = NO_KEY
                effect = f"lock {self._locks_open - 1} opened; key consumed"
        elif binding == "force_latch":
            if self._solved():
                applicable = False
                effect = "all locks already open"
            elif self._rack_jammed:
                # Forcing works by wrecking the rack mechanism; once wrecked
                # there is nothing left to force against. Without this guard
                # `force_latch` was repeatable and opened the WHOLE chain,
                # which contradicted both this module's docstring and
                # `_dead_end` (which reports the position unreachable while
                # a repeated force in fact reached it). The environment was
                # internally inconsistent; this restores the documented
                # semantics -- force is a one-shot trap, not a solution.
                applicable = False
                effect = "rack already jammed: nothing left to force"
            else:
                self._locks_open += 1
                self._held = NO_KEY
                self._rack_jammed = True
                effect = f"lock {self._locks_open - 1} forced; rack jammed irreversibly"
        elif binding == "read_locks":
            effect = repr(self._state())
        else:
            raise ValueError(f"unsupported lock-and-key binding: {binding}")
        after = self._state()
        return {
            "before": before,
            "after": after,
            "applicable": applicable,
            "result_text": effect,
        }

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._state()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "locks_open": self._locks_open,
            "held_key": self._held,
            "rack_jammed": self._rack_jammed,
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._locks_open = int(checkpoint["locks_open"])
        self._held = int(checkpoint["held_key"])
        self._rack_jammed = bool(checkpoint["rack_jammed"])

    async def teardown(self) -> None:
        self._closed = True


class LockAndKeyProvider:
    """GymAct `EnvironmentProvider` materializing seeded lock chains."""

    name = "lock-and-key"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> LockAndKeyEnvironment:
        del scenario
        seed = config.get("seed", 0)
        depth = config.get("depth", 3)
        for label, value in (("seed", seed), ("depth", depth)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"config.{label} must be an int")
        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return LockAndKeyEnvironment(
            seed=seed, depth=depth, requires_authority=requires_authority
        )
