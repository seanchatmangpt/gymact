"""Bounded, self-contained local gym: a seeded switchboard with conditional,
negative, and decoy effects.

Structurally distinct from `cube_counter` (monotone counter, one effect per
action) in three ways a discovery agent must actually notice:

* **Conditional effect** -- `engage_master` only has an effect when switches 0
  and 1 are both on; otherwise it is applicable-and-inert.
* **Negative effect** -- `reset_pair` turns switches 0 and 1 *off*, undoing
  progress. It is lawful and always applicable, so it is a real trap.
* **Decoys** -- switches at indices >= 2 are mostly irrelevant; a seeded subset
  is genuinely required by the goal and the rest never matter.

Pure Python, no network, no Docker, no optional packages -- unlike
`cube_counter`, this module has no import-time dependency to skip on.
"""

from __future__ import annotations

import random
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

SWITCHBOARD_CAPABILITIES = (
    Capability(
        iri="urn:gymact:switchboard:capability:toggle_switch",
        title="Toggle one switch by index (payload: {'index': int})",
        consequence=Consequence.DO,
        binding="toggle_switch",
    ),
    Capability(
        iri="urn:gymact:switchboard:capability:engage_master",
        title="Engage the master latch; has effect only if switches 0 and 1 are both on",
        consequence=Consequence.DO,
        binding="engage_master",
    ),
    Capability(
        iri="urn:gymact:switchboard:capability:reset_pair",
        title="Turn switches 0 and 1 off (negative effect; always applicable)",
        consequence=Consequence.DO,
        binding="reset_pair",
    ),
    Capability(
        iri="urn:gymact:switchboard:capability:read_board",
        title="Read the switchboard's current configuration",
        consequence=Consequence.READ,
        binding="read_board",
    ),
)


class SwitchboardEnvironment:
    """N boolean switches plus a latch, with a seeded required-decoy pattern."""

    def __init__(
        self, *, seed: int, n_switches: int, requires_authority: bool = False
    ) -> None:
        if n_switches < 3:
            raise ValueError("switchboard requires n_switches >= 3")
        self.environment_id = f"urn:gymact:switchboard:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self.seed = seed
        self.n_switches = n_switches
        rng = random.Random(seed)
        pool = list(range(2, n_switches))
        k = min(2, len(pool))
        self.required: tuple[int, ...] = tuple(sorted(rng.sample(pool, k))) if k else ()
        self._switches = [False] * n_switches
        self._master = False
        self._toggles = 0
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return SWITCHBOARD_CAPABILITIES

    def _required_on(self) -> int:
        return sum(1 for i in self.required if self._switches[i])

    def _solved(self) -> bool:
        return self._master and self._required_on() == len(self.required)

    def _state(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            f"switch_{i}": bool(value) for i, value in enumerate(self._switches)
        }
        state.update(
            {
                "master": self._master,
                "n_switches": self.n_switches,
                "toggles": self._toggles,
                "required_count": len(self.required),
                "required_on": self._required_on(),
                "solved": self._solved(),
            }
        )
        return state

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before = self._state()
        binding = capability.binding
        applicable = True
        if binding == "toggle_switch":
            index = int(payload["index"])
            if not 0 <= index < self.n_switches:
                raise ValueError(f"switch index out of range: {index}")
            self._switches[index] = not self._switches[index]
            self._toggles += 1
            effect = f"switch_{index}={self._switches[index]}"
        elif binding == "engage_master":
            if self._switches[0] and self._switches[1]:
                self._master = True
                effect = "master engaged"
            else:
                applicable = False
                effect = "precondition unmet: switches 0 and 1 must both be on"
        elif binding == "reset_pair":
            self._switches[0] = False
            self._switches[1] = False
            effect = "switches 0 and 1 forced off"
        elif binding == "read_board":
            effect = repr(self._state())
        else:
            raise ValueError(f"unsupported switchboard binding: {binding}")
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
            "switches": list(self._switches),
            "master": self._master,
            "toggles": self._toggles,
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        """Restore from a real checkpoint dict -- validated against this
        environment's own `n_switches` before it becomes live state.

        Real bug found and fixed forward this session (FMEA #1, RPN 324):
        an unvalidated `checkpoint["switches"]` of the wrong length used to
        be accepted here unchecked, silently desynchronizing `_switches`
        from `n_switches`. That corrupted state then crashed the
        unprotected `observe()` path later: `_state()` -> `_required_on()`
        indexes into `self._switches` at `self.required`'s indices (which
        are only guaranteed `< n_switches`), raising an uncaught
        `IndexError` on the very next `observe()` call -- far from the real
        root cause (`restore()` accepting bad input). Validating length and
        element types here, at the actual point of untrusted input, turns
        that into an immediate, honest `ValueError` instead of a deferred
        crash on an unrelated read path.
        """
        self._ensure_open()
        switches = checkpoint.get("switches")
        if not isinstance(switches, list) or len(switches) != self.n_switches:
            raise ValueError(
                f"checkpoint.switches must be a list of length {self.n_switches}, "
                f"got {switches!r}"
            )
        if "master" not in checkpoint or "toggles" not in checkpoint:
            raise ValueError("checkpoint must contain 'master' and 'toggles'")
        self._switches = [bool(v) for v in switches]
        self._master = bool(checkpoint["master"])
        self._toggles = int(checkpoint["toggles"])

    async def teardown(self) -> None:
        self._closed = True


class SwitchboardProvider:
    """GymAct `EnvironmentProvider` materializing seeded switchboards."""

    name = "switchboard"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> SwitchboardEnvironment:
        del scenario
        seed = config.get("seed", 0)
        n_switches = config.get("n_switches", 5)
        for label, value in (("seed", seed), ("n_switches", n_switches)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"config.{label} must be an int")
        requires_authority = config.get("requires_authority", False)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return SwitchboardEnvironment(
            seed=seed, n_switches=n_switches, requires_authority=requires_authority
        )
