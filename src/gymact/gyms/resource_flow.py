"""Bounded, self-contained local gym: capacitated token pools with a real,
irreversible dead end.

Structurally distinct from `cube_counter` and `switchboard`:

* **Numeric resource semantics** -- actions *consume* from one pool and
  *produce* into another, and every pool is capped at `capacity`, so an action
  can be refused for a full destination as well as an empty source.
* **Irreversible consumption** -- `burn_catalyst` destroys the single catalyst
  token for a one-off output bonus. `refine` requires the catalyst, so after
  burning it the refine step is permanently impossible: if the output pool is
  still short of `target` at that point, the episode is in a genuine dead end
  that no sequence of remaining actions can escape.

Pure Python, no network, no Docker, no optional packages.
"""

from __future__ import annotations

import random
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

RESOURCE_FLOW_CAPABILITIES = (
    Capability(
        iri="urn:gymact:resource-flow:capability:mine",
        title="Mine raw tokens into the raw pool (bounded by capacity)",
        consequence=Consequence.DO,
        binding="mine",
    ),
    Capability(
        iri="urn:gymact:resource-flow:capability:refine",
        title="Convert one raw token into one refined token; requires the catalyst",
        consequence=Consequence.DO,
        binding="refine",
    ),
    Capability(
        iri="urn:gymact:resource-flow:capability:assemble",
        title="Convert one refined token into one output token",
        consequence=Consequence.DO,
        binding="assemble",
    ),
    Capability(
        iri="urn:gymact:resource-flow:capability:burn_catalyst",
        title="Irreversibly burn the catalyst for a one-off output bonus; disables refine forever",
        consequence=Consequence.DO,
        binding="burn_catalyst",
    ),
    Capability(
        iri="urn:gymact:resource-flow:capability:read_pools",
        title="Read the current pool levels",
        consequence=Consequence.READ,
        binding="read_pools",
    ),
)


class ResourceFlowEnvironment:
    """Three capacitated pools (raw -> refined -> output) and one catalyst."""

    def __init__(
        self, *, seed: int, capacity: int, target: int, requires_authority: bool = False
    ) -> None:
        if capacity < 1:
            raise ValueError("resource-flow requires capacity >= 1")
        if not 1 <= target <= capacity:
            raise ValueError("resource-flow requires 1 <= target <= capacity")
        self.environment_id = f"urn:gymact:resource-flow:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self.seed = seed
        self.capacity = capacity
        self.target = target
        rng = random.Random(seed)
        self.mine_rate = rng.randint(1, 3)
        self.catalyst_bonus = rng.randint(1, 2)
        self._raw = 0
        self._refined = 0
        self._output = 0
        self._catalyst = True
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return RESOURCE_FLOW_CAPABILITIES

    def _dead_end(self) -> bool:
        """True when the goal is provably unreachable from here."""
        if self._output >= self.target:
            return False
        if self._catalyst:
            return False
        # Catalyst gone: refine is impossible forever, so the only remaining
        # source of output tokens is the refined pool already on hand.
        return self._output + self._refined < self.target

    def _state(self) -> dict[str, Any]:
        return {
            "raw": self._raw,
            "refined": self._refined,
            "output": self._output,
            "catalyst": self._catalyst,
            "capacity": self.capacity,
            "target": self.target,
            "mine_rate": self.mine_rate,
            "solved": self._output >= self.target,
            "dead_end": self._dead_end(),
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        before = self._state()
        binding = capability.binding
        applicable = True
        if binding == "mine":
            if self._raw >= self.capacity:
                applicable = False
                effect = "raw pool at capacity"
            else:
                gained = min(self.mine_rate, self.capacity - self._raw)
                self._raw += gained
                effect = f"mined {gained} raw"
        elif binding == "refine":
            if not self._catalyst:
                applicable = False
                effect = "catalyst burned: refine is permanently unavailable"
            elif self._raw < 1:
                applicable = False
                effect = "no raw tokens to refine"
            elif self._refined >= self.capacity:
                applicable = False
                effect = "refined pool at capacity"
            else:
                self._raw -= 1
                self._refined += 1
                effect = "refined 1 raw -> 1 refined"
        elif binding == "assemble":
            if self._refined < 1:
                applicable = False
                effect = "no refined tokens to assemble"
            elif self._output >= self.capacity:
                applicable = False
                effect = "output pool at capacity"
            else:
                self._refined -= 1
                self._output += 1
                effect = "assembled 1 refined -> 1 output"
        elif binding == "burn_catalyst":
            if not self._catalyst:
                applicable = False
                effect = "catalyst already burned"
            else:
                self._catalyst = False
                gained = min(self.catalyst_bonus, self.capacity - self._output)
                self._output += gained
                effect = f"catalyst burned irreversibly for {gained} output"
        elif binding == "read_pools":
            effect = repr(self._state())
        else:
            raise ValueError(f"unsupported resource-flow binding: {binding}")
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
            "raw": self._raw,
            "refined": self._refined,
            "output": self._output,
            "catalyst": self._catalyst,
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        """Restore from a real checkpoint dict -- validated against this
        environment's own `capacity` before it becomes live state.

        Real bug found and fixed forward this round (RCA RPN 432, same class
        as `switchboard.py`'s already-fixed restore bug and
        `lock_and_key.py`'s companion fix this round): an unvalidated
        `output`/`raw`/`refined` used to be accepted here unchecked, so a
        checkpoint claiming e.g. `output=999 > capacity=5` would silently
        become live state and `_solved()` could then report a false
        `solved=True` for an out-of-bound, physically impossible pool level.
        Validating bounds here, at the actual point of untrusted input, turns
        that into an immediate, honest `ValueError` instead of a
        false-positive solved report.
        """
        self._ensure_open()
        raw = int(checkpoint["raw"])
        refined = int(checkpoint["refined"])
        output = int(checkpoint["output"])
        for name, value in (("raw", raw), ("refined", refined), ("output", output)):
            if not 0 <= value <= self.capacity:
                raise ValueError(
                    f"checkpoint.{name} must be in [0, {self.capacity}], got {value!r}"
                )
        self._raw = raw
        self._refined = refined
        self._output = output
        self._catalyst = bool(checkpoint["catalyst"])

    async def teardown(self) -> None:
        self._closed = True


class ResourceFlowProvider:
    """GymAct `EnvironmentProvider` materializing seeded capacitated flows."""

    name = "resource-flow"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> ResourceFlowEnvironment:
        del scenario
        seed = config.get("seed", 0)
        capacity = config.get("capacity", 8)
        target = config.get("target", 3)
        for label, value in (("seed", seed), ("capacity", capacity), ("target", target)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"config.{label} must be an int")
        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return ResourceFlowEnvironment(
            seed=seed,
            capacity=capacity,
            target=target,
            requires_authority=requires_authority,
        )
