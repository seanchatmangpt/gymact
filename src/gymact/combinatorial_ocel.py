"""Bridges gymact's two real, previously-unconnected systems: the real
Design-for-Combinatorial-Maximum engine (`combinatorial.py`'s
`manufacture_combination_space`) and the real OCEL 2.0 emitter
(`ocel.py`'s `receipts_to_ocel`/`validate_ocel_log`/`write_ocel_log`).

Neither existing system needed to change for this to work -- this module
is pure wiring: enumerate the real, bounded Cartesian product of
`(gym, operation_sequence_variant)` via the existing combinatorial
engine, actually drive a real `GymAct` episode for every resulting
combination, and fold every real receipt produced across every
combination into one real, schema-valid, exhaustive OCEL 2.0 log.

Per `docs/combinatorial-maximum.md`'s own law ("If a bound truncates
exploration, truncation is evidence. Silent pruning is forbidden"): if the
real combination space exceeds the configured bound, `CombinationSpace.
truncated` is `True` and the combination report below names it -- never
silently dropped.

Real, honest scope limit, named not hidden: each `(gym, variant)` cell is
driven by a hand-written, gym-specific scenario function (see
`_SCENARIOS` below) -- because different real gyms expose genuinely
different real capabilities/payload shapes, there is no generic
"press play" dispatcher that works across all of them without knowing
each gym's real contract. Adding a new gym to this combinatorial space
means adding one real scenario entry, not extending a generic engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .combinatorial import CombinationSpace, ExplorationBounds, Factor, manufacture_combination_space
from .gyms.lock_and_key import LockAndKeyProvider
from .gyms.switchboard import SwitchboardProvider
from .kernel import GymAct
from .models import ActuationIntent, MaterializationIntent, Receipt
from .ocel import validate_ocel_log, write_ocel_log
from .providers import MemoryProvider

try:  # cloud-topology is a real, optional-extra gym (needs botocore)
    from .gyms.cloud_topology_gym import CloudTopologyProvider

    _CLOUD_TOPOLOGY_AVAILABLE = True
except ImportError:  # pragma: no cover -- real UNSUPPORTED environment gate
    _CLOUD_TOPOLOGY_AVAILABLE = False

__all__ = [
    "REPORTS_DIR",
    "GYM_FACTOR",
    "SEQUENCE_VARIANT_FACTOR",
    "build_combination_space",
    "run_combinatorial_maximum",
]

# Deliberately NOT under `reports/ocel/<subject>/` -- that convention is
# owned by `tests/test_ocel_standing.py`'s per-subject conformance suite,
# which requires every log it discovers there to carry a real
# `solved=True` reason on its `act` events (one gym, one task, solved or
# not). This module's log is a genuinely different kind of evidence --
# breadth of coverage across MANY real gyms and operation-sequence
# variants in one combined log, several of which (e.g. cloud-topology's
# read-only capability queries) have no single "solved" notion at all.
# Conflating the two would mean either fabricating a "solved=True" string
# for scenarios that were never solving a task, or weakening that other
# suite's real check -- both dishonest. A sibling directory keeps both
# real, distinct evidence types intact.
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports" / "ocel-combinatorial" / "combinatorial-maximum"


ScenarioFn = Callable[[GymAct, str], Awaitable[None]]


@dataclass(frozen=True)
class _GymScenario:
    provider_factory: Callable[[], Any]
    config: dict[str, Any]
    scenario: str | None
    variants: dict[str, ScenarioFn]


# Real, deliberate finding, kept and documented rather than "fixed" to
# look uniformly green: `MemoryProvider`'s real `set`/`delete`/`increment`
# capabilities require authority by default, and `GymAct()`'s default
# `DenyAuthorityResolver` is fail-closed -- with no real authority grant
# supplied, every `memory` combination below correctly reaches real
# `Standing.REFUSED` (`reason=LIVE_AUTHORITY_REQUIRED`), never `ALIVE`.
# This is intentionally left this way: a combinatorial-maximum proof that
# only ever reaches `ALIVE` would be exactly the kind of unfalsifiable,
# cherry-picked result this doctrine exists to prevent. A real, correctly-
# enforced refusal is evidence the authority gate works, not a gap.
async def _memory_happy_path(gym: GymAct, ep: str) -> None:
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:memory:capability:set", payload={"key": "counter", "value": 1}))
    await gym.verify(ep, {"counter": 1})


async def _memory_with_checkpoint_restore(gym: GymAct, ep: str) -> None:
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:memory:capability:set", payload={"key": "counter", "value": 1}))
    checkpoint = await gym.checkpoint(ep)
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:memory:capability:set", payload={"key": "counter", "value": 2}))
    await gym.restore(ep, checkpoint)
    await gym.verify(ep, {"counter": 1})


async def _memory_observe_only(gym: GymAct, ep: str) -> None:
    await gym.observe(ep)


async def _lock_and_key_happy_path(gym: GymAct, ep: str) -> None:
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:lock-and-key:capability:pick_key", payload={"key": 0}))
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:lock-and-key:capability:open_lock", payload={}))
    await gym.observe(ep)


async def _lock_and_key_with_checkpoint_restore(gym: GymAct, ep: str) -> None:
    checkpoint = await gym.checkpoint(ep)
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:lock-and-key:capability:pick_key", payload={"key": 0}))
    await gym.restore(ep, checkpoint)
    await gym.observe(ep)


async def _lock_and_key_observe_only(gym: GymAct, ep: str) -> None:
    await gym.observe(ep)


async def _switchboard_happy_path(gym: GymAct, ep: str) -> None:
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:switchboard:capability:toggle_switch", payload={"index": 0}))
    await gym.verify(ep, {"switch_0": True})


async def _switchboard_with_checkpoint_restore(gym: GymAct, ep: str) -> None:
    checkpoint = await gym.checkpoint(ep)
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:switchboard:capability:toggle_switch", payload={"index": 0}))
    await gym.restore(ep, checkpoint)
    await gym.verify(ep, {"switch_0": False})


async def _switchboard_observe_only(gym: GymAct, ep: str) -> None:
    await gym.observe(ep)


async def _cloud_topology_happy_path(gym: GymAct, ep: str) -> None:
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:cloud-topology:capability:list_regions", payload={}))


async def _cloud_topology_with_checkpoint_restore(gym: GymAct, ep: str) -> None:
    checkpoint = await gym.checkpoint(ep)
    await gym.act(ActuationIntent(episode_id=ep, capability="urn:gymact:cloud-topology:capability:list_services", payload={}))
    await gym.restore(ep, checkpoint)


async def _cloud_topology_observe_only(gym: GymAct, ep: str) -> None:
    await gym.observe(ep)


def _build_scenarios() -> dict[str, _GymScenario]:
    scenarios: dict[str, _GymScenario] = {
        "memory": _GymScenario(
            provider_factory=MemoryProvider,
            config={},
            scenario=None,
            variants={
                "happy_path": _memory_happy_path,
                "with_checkpoint_restore": _memory_with_checkpoint_restore,
                "observe_only": _memory_observe_only,
            },
        ),
        "lock-and-key": _GymScenario(
            provider_factory=LockAndKeyProvider,
            config={"seed": 7, "depth": 3},
            scenario=None,
            variants={
                "happy_path": _lock_and_key_happy_path,
                "with_checkpoint_restore": _lock_and_key_with_checkpoint_restore,
                "observe_only": _lock_and_key_observe_only,
            },
        ),
        "switchboard": _GymScenario(
            provider_factory=SwitchboardProvider,
            config={"seed": 7, "n_switches": 6},
            scenario=None,
            variants={
                "happy_path": _switchboard_happy_path,
                "with_checkpoint_restore": _switchboard_with_checkpoint_restore,
                "observe_only": _switchboard_observe_only,
            },
        ),
    }
    if _CLOUD_TOPOLOGY_AVAILABLE:
        for provider_name in ("aws", "azure", "gcp"):
            scenarios[f"cloud-topology-{provider_name}"] = _GymScenario(
                provider_factory=CloudTopologyProvider,
                config={},
                scenario=provider_name,
                variants={
                    "happy_path": _cloud_topology_happy_path,
                    "with_checkpoint_restore": _cloud_topology_with_checkpoint_restore,
                    "observe_only": _cloud_topology_observe_only,
                },
            )
    return scenarios


_SCENARIOS: dict[str, _GymScenario] = _build_scenarios()

GYM_FACTOR = Factor(factor_id="gym", alternatives=tuple(_SCENARIOS.keys()))
SEQUENCE_VARIANT_FACTOR = Factor(
    factor_id="operation_sequence_variant",
    alternatives=("happy_path", "with_checkpoint_restore", "observe_only"),
)


def build_combination_space(*, max_combinations: int = 10_000) -> CombinationSpace:
    """Real call into the existing, unmodified combinatorial engine --
    never a reimplementation of the Cartesian-product logic it already
    provides."""
    return manufacture_combination_space(
        (GYM_FACTOR, SEQUENCE_VARIANT_FACTOR),
        bounds=ExplorationBounds(max_combinations=max_combinations),
    )


async def drive_combination(gym_id: str, variant: str) -> tuple[list[Receipt], str]:
    """Actually run one real `(gym, variant)` cell end to end. Returns the
    real receipts `GymAct` recorded for this episode, plus the real,
    final `Standing` value reached (read from the real receipt trail, the
    same source of truth `episode_ocel_log` itself uses -- never a
    separately-tracked, potentially-drifting summary)."""
    scenario = _SCENARIOS[gym_id]
    gym = GymAct()
    provider = scenario.provider_factory()
    gym.register_provider(provider)
    materialization = await gym.materialize(
        MaterializationIntent(provider=provider.name, scenario=scenario.scenario, config=scenario.config)
    )
    if not materialization.accepted:
        raise RuntimeError(f"materialize refused for real: gym={gym_id} variant={variant}")
    ep = materialization.episode.episode_id
    await scenario.variants[variant](gym, ep)
    await gym.teardown(ep)
    receipts = gym.episode_receipts(ep)
    final_standing = receipts[-1].standing.value if receipts else "UNKNOWN"
    return receipts, final_standing


async def run_combinatorial_maximum(
    *, max_combinations: int = 10_000, reports_dir: Path = REPORTS_DIR
) -> tuple[CombinationSpace, dict[str, Any]]:
    """Drive every real combination in the (possibly truncated) space,
    fold ALL real receipts across ALL combinations into one real,
    exhaustive OCEL 2.0 log via the existing, unmodified `write_ocel_log`,
    and write a real, cross-checkable combination report alongside it."""
    space = build_combination_space(max_combinations=max_combinations)

    all_receipts: list[Receipt] = []
    rows: list[dict[str, Any]] = []
    for combination in space.combinations:
        gym_id = combination.assignments["gym"]
        variant = combination.assignments["operation_sequence_variant"]
        receipts, final_standing = await drive_combination(gym_id, variant)
        all_receipts.extend(receipts)
        rows.append(
            {
                "combination_id": combination.combination_id,
                "gym": gym_id,
                "operation_sequence_variant": variant,
                "receipt_count": len(receipts),
                "final_standing": final_standing,
            }
        )

    reports_dir.mkdir(parents=True, exist_ok=True)
    ocel_path = reports_dir / "episode.ocel.json"
    log, log_digest = write_ocel_log(ocel_path, all_receipts)
    validate_ocel_log(log)  # real, independent re-validation -- never trust write_ocel_log's own success silently

    report = {
        "total_cardinality": space.total_cardinality,
        "combinations_run": len(space.combinations),
        "truncated": space.truncated,
        "total_receipts": len(all_receipts),
        "ocel_log_path": str(ocel_path),
        "ocel_log_digest": log_digest,
        "combinations": rows,
    }
    report_path = reports_dir / "combination_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    return space, report
