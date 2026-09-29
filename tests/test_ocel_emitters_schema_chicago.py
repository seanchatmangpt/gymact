"""Chicago-style completeness + schema court for OCEL emitters.

Mirrors `tests/test_registry_completeness_chicago.py` and
`tests/test_composition_inventory_completeness_chicago.py`: mechanically ask
"what OCEL emitters actually exist?" and require each discovered emitter to be
EITHER exercised here with real minimal input (its output validated against the
real official OCEL 2.0 JSON Schema via `gymact.ocel.validate_ocel_log`, with
assertions on real returned content) OR named in `_INTENTIONALLY_UNCOVERED`
with a specific, honest reason.

Motivation: a policy-ecology OCEL emitter once shipped output that failed the
official schema (object-attribute `time` missing; non-string event values)
because nothing validated it. The schema is only a real gate if every emitter
is actually driven through it.

Discovery rule (AST, `src/gymact`, excluding `explore_*` packages): any
function/method whose name contains `to_ocel` or `ocel_log` (which subsumes
`*_events_to_ocel`) AND whose return annotation mentions `dict` (a bare
`dict[str, Any]` log, or a tuple wrapper such as `tuple[dict[str, Any], str]`).
Matching names returning `str`/`None` (`digest_ocel_log`, `validate_ocel_log`)
are not emitters and are asserted excluded, so the rule stays precise.

Second, content-based detector (added alongside, not replacing, the name rule):
any function/method with a return annotation mentioning `dict` or
`OCELGymResult` whose OWN body (nested defs excluded) either builds a dict
literal shaped like an OCEL log (keys `events`+`objects`, or
`eventTypes`+`objectTypes`), calls a known OCEL producer/validator
(`validate_ocel_log`, `digest_ocel_log`, `write_ocel_log`, `receipts_to_ocel`,
`manufacture_ocel_history`, `to_ocel_log`, `GymactOcelSessionRecorder`), or is
annotated to return an `OCELGymResult`. Docstring/name mentions of "ocel" are
deliberately NOT a signal (`cost_ledger.sum_costs_by_unit` is the precision
witness). The court's discovered set is the union of both detectors.

Scope limit, stated honestly: both detectors are syntactic. An emitter that
neither matches the name pattern nor builds a log-shaped dict literal nor calls
one of the named producers (e.g. one that only forwards an OCEL dict it got
elsewhere, like `OCELGymResult.operational_view`, or a method returning a
cached `self.log`) is still out of reach. `gymact.runtime_evolution.ocel.*`
`receipt()` methods are bounded runtime-evolution stubs that return a small
receipt dict with no OCEL `events`/`objects`; they are not OCEL emitters and
are asserted not discovered.

No collaborator is faked: real `GymAct` memory episode, real Pydantic events,
real `DspyOcelCallback` hooks driven directly (no network, no LM), real
`ast` scans over real and temporary source trees.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from gymact import (
    ActuationIntent,
    AllowListAuthorityResolver,
    GymAct,
    MaterializationIntent,
    MemoryProvider,
)
from gymact.combinatorial_ocel import run_combinatorial_maximum
from gymact.execution_loop import EpisodeStanding, LoopResult, OcelEvent, loop_log
from gymact.manufacture import manufacture_synthetic_ocel_result
from gymact.models import CostDimension, Receipt, Standing
from gymact.ocel import receipts_to_ocel, validate_ocel_log, write_ocel_log
from gymact.policy_ecology_ocel import (
    PolicyEcologyEvent,
    PolicyEcologyEventType,
    policy_ecology_events_to_ocel,
)
from gymact.powl.algebra import Atom, OrderEdge, PartialOrder
from gymact.powl.ocel_bridge import GymactOcelSessionRecorder
from gymact.powl.runner import run_pipeline
from gymact.powl.spec import PowlPipelineSpec
from gymact.synthetic_ocel import (
    OCELTraceOrigin,
    executed_ocel_result,
    manufacture_ocel_history,
    observed_ocel_result,
)

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "gymact"

AUTHORITY = "urn:test:ocel-emitters-authority"
SET_CAPABILITY = "urn:gymact:memory:capability:set"

_NAME_PATTERN = re.compile(r"to_ocel|ocel_log")
_OCEL_KEYS_A = frozenset({"events", "objects"})
_OCEL_KEYS_B = frozenset({"eventTypes", "objectTypes"})
_OCEL_CALLEE = re.compile(
    r"^(validate_ocel_log|digest_ocel_log|write_ocel_log|receipts_to_ocel"
    r"|manufacture_ocel_history|to_ocel_log|GymactOcelSessionRecorder)$"
)


# ---------------------------------------------------------------------------
# Discovery: injectable scan root so a control can run on a tmp tree.
# ---------------------------------------------------------------------------


def _is_excluded(path: Path, root: Path) -> bool:
    return any(part.startswith("explore_") for part in path.relative_to(root).parts)


def _walk_defs(root: Path) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Yield (qualname, node) for every module-level function and class method
    under `root` (nested defs are implementation detail), skipping `explore_*`."""
    for py_file in sorted(root.rglob("*.py")):
        if _is_excluded(py_file, root):
            continue
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        rel = py_file.relative_to(root.parent).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = ".".join(parts)

        def visit(
            node: ast.AST, scope: tuple[str, ...], module: str = module
        ) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    yield from visit(child, (*scope, child.name))
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield ".".join([module, *scope, child.name]), child

        yield from visit(tree, ())


def _discover_emitters(root: Path) -> dict[str, str]:
    """qualname -> return annotation source, for every OCEL-emitter-shaped def
    (NAME detector: `to_ocel|ocel_log` in the name AND a `dict` return annotation).

    qualname is `<module.path>.<[Class.]function>` with the module path derived
    from the file path relative to `root`'s parent (so the real tree yields
    `gymact.ocel.receipts_to_ocel`).
    """
    found: dict[str, str] = {}
    for qualname, node in _walk_defs(root):
        if _NAME_PATTERN.search(node.name) and node.returns is not None:
            annotation = ast.unparse(node.returns)
            if "dict" in annotation:
                found[qualname] = annotation
    return found


def _own_nodes(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[ast.AST]:
    """Every node in `fn`'s own body, not descending into nested defs/classes."""
    nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    stack: list[ast.AST] = [n for n in fn.body if not isinstance(n, nested)]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(c for c in ast.iter_child_nodes(node) if not isinstance(c, nested))


def _discover_content_emitters(root: Path) -> dict[str, str]:
    """qualname -> return annotation source (CONTENT detector; see module docstring)."""
    found: dict[str, str] = {}
    for qualname, node in _walk_defs(root):
        if node.returns is None:
            continue
        annotation = ast.unparse(node.returns)
        if "dict" not in annotation and "OCELGymResult" not in annotation:
            continue
        signal = "OCELGymResult" in annotation
        for child in _own_nodes(node):
            if isinstance(child, ast.Dict):
                keys = {
                    k.value
                    for k in child.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                }
                signal = signal or keys >= _OCEL_KEYS_A or keys >= _OCEL_KEYS_B
            elif isinstance(child, ast.Call):
                fn = child.func
                callee = (
                    fn.id
                    if isinstance(fn, ast.Name)
                    else fn.attr
                    if isinstance(fn, ast.Attribute)
                    else ""
                )
                signal = signal or bool(_OCEL_CALLEE.match(callee))
        if signal:
            found[qualname] = annotation
    return found


def _discover_all_emitters(root: Path) -> dict[str, str]:
    """Union of the name detector and the content detector."""
    return {**_discover_content_emitters(root), **_discover_emitters(root)}


def _unaccounted(discovered: set[str], covered: set[str], allowlist: dict[str, str]) -> list[str]:
    return sorted(discovered - covered - set(allowlist))


def _stale(discovered: set[str], covered: set[str], allowlist: dict[str, str]) -> list[str]:
    return sorted((set(allowlist) | covered) - discovered)


# ---------------------------------------------------------------------------
# Real inputs.
# ---------------------------------------------------------------------------


async def _real_memory_episode() -> tuple[GymAct, str, list[Receipt]]:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(MemoryProvider())
    materialized = await gym.materialize(
        MaterializationIntent(
            provider="memory",
            config={"initial": {"safe": False}, "requires_authority": True},
            idempotency_key="ocel-emitters-materialize",
        )
    )
    assert materialized.accepted is True
    assert materialized.episode is not None
    episode_id = materialized.episode.episode_id
    acted = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=SET_CAPABILITY,
            payload={"key": "safe", "value": True},
            authority_ref=AUTHORITY,
            idempotency_key="ocel-emitters-act",
        )
    )
    assert acted.accepted is True
    return gym, episode_id, gym.episode_receipts(episode_id)


def _policy_events() -> tuple[PolicyEcologyEvent, ...]:
    return (
        PolicyEcologyEvent(
            event_id="ev-manufacture",
            event_type=PolicyEcologyEventType.MANUFACTURE,
            occurred_at="2026-01-01T00:00:00Z",
            population_digest="pop-root",
            population_kind="root",
            attributes={"size": 4, "seeded": True, "scale": 0.5, "label": "x"},
        ),
        PolicyEcologyEvent(
            event_id="ev-condition",
            event_type=PolicyEcologyEventType.CONDITION,
            occurred_at="2026-01-01T00:01:00Z",
            population_digest="pop-child",
            population_kind="conditioned",
            parent_population_digest="pop-root",
            cue=0.25,
            design_ref="urn:gymact:design:d1",
            evidence_refs=("urn:gymact:evidence:e1",),
        ),
    )


def _assert_all_strings(log: dict[str, Any]) -> None:
    for event in log["events"]:
        for attribute in event["attributes"]:
            assert isinstance(attribute["value"], str), (event["id"], attribute)


# ---------------------------------------------------------------------------
# Coverage tests: one per emitter. Registry below maps qualname -> test name.
# ---------------------------------------------------------------------------


async def test_receipts_to_ocel_schema_valid_with_real_content() -> None:
    _, episode_id, receipts = await _real_memory_episode()
    log = receipts_to_ocel(receipts)
    validate_ocel_log(log)
    assert len(receipts) >= 2
    assert len(log["events"]) == len(receipts)
    assert {e["id"] for e in log["events"]} == {r.receipt_id for r in receipts}
    assert episode_id in {o["id"] for o in log["objects"] if o["type"] == "episode"}
    _assert_all_strings(log)


async def test_receipts_to_ocel_costed_receipt_is_schema_valid_and_round_trips() -> None:
    """A receipt carrying a float cost once produced a schema-invalid log
    (event attribute values must be strings); this pins the costed path."""
    _, _, receipts = await _real_memory_episode()
    costed = receipts[0].model_copy(
        update={
            "costs": (
                CostDimension(
                    unit="usd", quantity=1.5, kind="observed_actual", source="test-measured"
                ),
            )
        }
    )
    log = receipts_to_ocel([costed, *receipts[1:]])
    validate_ocel_log(log)
    event = next(e for e in log["events"] if e["id"] == costed.receipt_id)
    by_name = {a["name"]: a["value"] for a in event["attributes"]}
    assert by_name["cost:usd"] == "1.5"
    assert float(by_name["cost:usd"]) == 1.5
    _assert_all_strings(log)


async def test_episode_ocel_log_schema_valid_with_real_content() -> None:
    gym, episode_id, receipts = await _real_memory_episode()
    log = gym.episode_ocel_log(episode_id)
    validate_ocel_log(log)
    assert len(log["events"]) == len(receipts)
    assert episode_id in {o["id"] for o in log["objects"]}


async def test_write_ocel_log_schema_valid_with_real_content(tmp_path: Path) -> None:
    _, _, receipts = await _real_memory_episode()
    path = tmp_path / "episode.ocel.json"
    log, digest = write_ocel_log(path, receipts)
    validate_ocel_log(log)
    assert len(log["events"]) == len(receipts)
    assert len(digest) == 64 and path.is_file()


def test_policy_ecology_events_to_ocel_schema_valid_with_real_content() -> None:
    log = policy_ecology_events_to_ocel(_policy_events())
    validate_ocel_log(log)
    assert [e["id"] for e in log["events"]] == ["ev-manufacture", "ev-condition"]
    assert {o["id"] for o in log["objects"]} == {"pop-root", "pop-child"}
    # Regression for the shipped defect: every object attribute carries `time`.
    for obj in log["objects"]:
        for attribute in obj["attributes"]:
            assert isinstance(attribute["time"], str) and attribute["time"]
    _assert_all_strings(log)
    values = {a["name"]: a["value"] for a in log["events"][0]["attributes"]}
    assert values["seeded"] == "true" and values["size"] == "4" and values["scale"] == "0.5"


def _drive_dspy_callback() -> Any:
    pytest.importorskip("dspy")
    from gymact.dspy_ocel import DspyOcelCallback

    class _Named:
        def __init__(self, **kw: Any) -> None:
            self.__dict__.update(kw)

    callback = DspyOcelCallback(run_id="run-emitters-1")
    callback.on_lm_start("c1", _Named(model="test/model"), {"prompt": "hi"})
    callback.on_lm_end("c1", {"answer": "ok"})
    callback.on_tool_start("c2", _Named(name="kubectl"), {"cmd": "get pods"})
    callback.on_tool_end("c2", None, exception=RuntimeError("boom"))
    callback.on_module_start("c3", _Named(), {"q": 1})
    callback.on_module_end("c3", {"a": 2})
    return callback


def _assert_dspy_log(log: dict[str, Any]) -> None:
    validate_ocel_log(log)
    assert [e["id"] for e in log["events"]] == ["c1", "c2", "c3"]
    assert {o["id"] for o in log["objects"]} >= {"run-emitters-1", "test/model", "kubectl"}
    _assert_all_strings(log)
    failed = {
        e["id"]: next(a["value"] for a in e["attributes"] if a["name"] == "failed")
        for e in log["events"]
    }
    assert failed == {"c1": "False", "c2": "True", "c3": "False"}


def test_dspy_to_ocel_log_schema_valid_with_real_content() -> None:
    _assert_dspy_log(_drive_dspy_callback().to_ocel_log())


def test_build_and_validate_dspy_ocel_log_schema_valid_with_real_content() -> None:
    pytest.importorskip("dspy")
    from gymact.dspy_ocel import build_and_validate_dspy_ocel_log

    log, digest = build_and_validate_dspy_ocel_log(_drive_dspy_callback())
    _assert_dspy_log(log)
    assert len(digest) == 64


def test_write_dspy_ocel_log_schema_valid_with_real_content(tmp_path: Path) -> None:
    pytest.importorskip("dspy")
    from gymact.dspy_ocel import write_dspy_ocel_log

    path = tmp_path / "dspy.ocel.json"
    log, digest = write_dspy_ocel_log(path, _drive_dspy_callback())
    _assert_dspy_log(log)
    assert len(digest) == 64 and path.is_file()


# --- Content-detector emitters (names the name rule cannot see) -------------


def test_loop_log_schema_valid_with_real_content() -> None:
    results = [
        LoopResult(
            outcome="Recover",
            standing=Standing.ALIVE,
            episode_standing=EpisodeStanding.AUTONOMOUS,
            events=[
                OcelEvent(
                    event_type="execution.start",
                    tick=0,
                    attributes={"provider": "p1", "attempt": 1},
                    objects={"subject": "repo-a", "provider": "p1"},
                ),
                OcelEvent(
                    event_type="receipt.emit",
                    tick=5,
                    attributes={"outcome": "Recover"},
                    objects={"subject": "repo-a", "receipt": "r-1"},
                ),
            ],
        )
    ]
    log = loop_log(results, seed=7)
    validate_ocel_log(log)
    assert [e["type"] for e in log["events"]] == ["execution.start", "receipt.emit"]
    assert {(o["type"], o["id"]) for o in log["objects"]} == {
        ("subject", "repo-a"),
        ("provider", "p1"),
        ("receipt", "r-1"),
    }
    assert {t["name"] for t in log["eventTypes"]} == {"execution.start", "receipt.emit"}
    first = {a["name"]: a["value"] for a in log["events"][0]["attributes"]}
    assert first == {"attempt": "1", "provider": "p1", "seed": "7"}
    _assert_all_strings(log)
    # Deterministic: same inputs and seed give the identical log.
    assert loop_log(results, seed=7) == log


async def test_run_combinatorial_maximum_schema_valid_with_real_content(tmp_path: Path) -> None:
    space, report = await run_combinatorial_maximum(max_combinations=3, reports_dir=tmp_path)
    log = json.loads((tmp_path / "episode.ocel.json").read_text())
    validate_ocel_log(log)
    assert report["combinations_run"] == len(space.combinations) == 3
    assert report["truncated"] is True
    assert report["total_receipts"] > 0
    assert len(log["events"]) == report["total_receipts"]
    assert sum(r["receipt_count"] for r in report["combinations"]) == len(log["events"])
    _assert_all_strings(log)


async def test_manufacture_ocel_history_schema_valid_with_real_content() -> None:
    _, _, receipts = await _real_memory_episode()
    spec = receipts_to_ocel(receipts)
    result = manufacture_ocel_history(
        history_spec=spec,
        claimed_actor="urn:test:planner",
        generator_spec={"g": 1},
        world_model={"w": 2},
        seed=11,
    )
    validate_ocel_log(result.log)
    assert result.log == spec and result.log is not spec  # copied, not aliased
    prov = result.provenance
    assert prov.origin is OCELTraceOrigin.GGEN_MANUFACTURED
    assert prov.observed_execution is False and prov.manufactured_trace is True
    assert prov.seed == 11 and prov.claimed_actor == "urn:test:planner"
    assert result.execution_receipt_refs == ()
    again = manufacture_ocel_history(
        history_spec=spec,
        claimed_actor="urn:test:planner",
        generator_spec={"g": 1},
        world_model={"w": 2},
        seed=11,
    )
    assert again.provenance == prov  # deterministic digests
    with pytest.raises(ValidationError):
        manufacture_ocel_history(
            history_spec={"events": [], "objects": []},
            claimed_actor="a",
            generator_spec=1,
            world_model=1,
            seed=1,
        )


async def test_manufacture_synthetic_ocel_result_schema_valid_with_real_content() -> None:
    _, _, receipts = await _real_memory_episode()
    spec = receipts_to_ocel(receipts)
    result = manufacture_synthetic_ocel_result(
        history_spec=spec,
        claimed_actor="urn:test:planner",
        generator_spec={"g": 1},
        world_model={"w": 2},
        seed="s",
        cursor="c1",
    )
    validate_ocel_log(result.log)
    assert result.log == spec
    assert result.cursor == "c1"
    assert result.provenance.origin is OCELTraceOrigin.GGEN_MANUFACTURED
    assert result.provenance.generator == "ggen"
    assert result.execution_receipt_refs == ()


async def test_executed_ocel_result_schema_valid_with_real_content() -> None:
    _, episode_id, receipts = await _real_memory_episode()
    result = executed_ocel_result(receipts)
    validate_ocel_log(result.log)
    assert result.execution_receipt_refs == tuple(r.receipt_id for r in receipts)
    assert {e["id"] for e in result.log["events"]} == {r.receipt_id for r in receipts}
    assert episode_id in {o["id"] for o in result.log["objects"]}
    assert result.provenance.origin is OCELTraceOrigin.GYM_EXECUTED
    assert result.provenance.observed_execution is True


async def test_observed_ocel_result_schema_valid_with_real_content() -> None:
    _, _, receipts = await _real_memory_episode()
    log = receipts_to_ocel(receipts)
    result = observed_ocel_result(log, source_ref="urn:test:real-system", claimed_actor="op")
    validate_ocel_log(result.log)
    assert result.log == log
    assert result.provenance.origin is OCELTraceOrigin.REAL_OBSERVED
    assert result.provenance.source_ref == "urn:test:real-system"
    assert result.execution_receipt_refs == ()
    with pytest.raises(ValidationError):
        observed_ocel_result({"events": []}, source_ref="urn:test:bad")


_POWL_SPEC = PowlPipelineSpec(
    readonly_labels=frozenset({"step_a", "step_b"}), default_session_id="emitters-court"
)


def _powl_model() -> PartialOrder:
    return PartialOrder(
        children=(Atom("step_a"), Atom("step_b")), order=frozenset({OrderEdge(0, 1)})
    )


def test_run_pipeline_schema_valid_with_real_content() -> None:
    log, stall = run_pipeline(
        _powl_model(), spec=_POWL_SPEC, session_id="sess-1", allow_partial_bindings=True
    )
    validate_ocel_log(log)
    assert stall.final
    assert [e["type"] for e in log["events"]] == ["powl_structural_fire"] * 2
    assert {o["id"] for o in log["objects"]} >= {"sess-1"}
    _assert_all_strings(log)


def test_powl_session_recorder_close_and_build_log_schema_valid_with_real_content() -> None:
    recorder = GymactOcelSessionRecorder("sess-2")
    recorder.record(
        activity="probe", objects=[("pod-1", "Pod")], outcome={"n": 3, "ok": True, "x": 0.5}
    )
    snapshot = recorder.log  # exercises the private `_build_log` builder
    closed = recorder.close()  # validates before returning
    validate_ocel_log(snapshot)
    validate_ocel_log(closed)
    assert snapshot == closed
    assert [e["type"] for e in closed["events"]] == ["probe"]
    assert {o["id"] for o in closed["objects"]} == {"sess-2", "pod-1"}
    values = {a["name"]: a["value"] for a in closed["events"][0]["attributes"]}
    assert values == {"n": "3", "ok": "True", "x": "0.5"}
    assert len(recorder.digest()) == 64
    _assert_all_strings(closed)


_COVERED: dict[str, str] = {
    "gymact.ocel.receipts_to_ocel": "test_receipts_to_ocel_schema_valid_with_real_content",
    "gymact.ocel.write_ocel_log": "test_write_ocel_log_schema_valid_with_real_content",
    "gymact.kernel.GymAct.episode_ocel_log": (
        "test_episode_ocel_log_schema_valid_with_real_content"
    ),
    "gymact.policy_ecology_ocel.policy_ecology_events_to_ocel": (
        "test_policy_ecology_events_to_ocel_schema_valid_with_real_content"
    ),
    "gymact.dspy_ocel.DspyOcelCallback.to_ocel_log": (
        "test_dspy_to_ocel_log_schema_valid_with_real_content"
    ),
    "gymact.dspy_ocel.build_and_validate_dspy_ocel_log": (
        "test_build_and_validate_dspy_ocel_log_schema_valid_with_real_content"
    ),
    "gymact.dspy_ocel.write_dspy_ocel_log": (
        "test_write_dspy_ocel_log_schema_valid_with_real_content"
    ),
    "gymact.execution_loop.loop_log": "test_loop_log_schema_valid_with_real_content",
    "gymact.combinatorial_ocel.run_combinatorial_maximum": (
        "test_run_combinatorial_maximum_schema_valid_with_real_content"
    ),
    "gymact.synthetic_ocel.manufacture_ocel_history": (
        "test_manufacture_ocel_history_schema_valid_with_real_content"
    ),
    "gymact.manufacture.manufacture_synthetic_ocel_result": (
        "test_manufacture_synthetic_ocel_result_schema_valid_with_real_content"
    ),
    "gymact.synthetic_ocel.executed_ocel_result": (
        "test_executed_ocel_result_schema_valid_with_real_content"
    ),
    "gymact.synthetic_ocel.observed_ocel_result": (
        "test_observed_ocel_result_schema_valid_with_real_content"
    ),
    "gymact.powl.runner.run_pipeline": "test_run_pipeline_schema_valid_with_real_content",
    "gymact.powl.ocel_bridge.GymactOcelSessionRecorder.close": (
        "test_powl_session_recorder_close_and_build_log_schema_valid_with_real_content"
    ),
    "gymact.powl.ocel_bridge.GymactOcelSessionRecorder._build_log": (
        "test_powl_session_recorder_close_and_build_log_schema_valid_with_real_content"
    ),
}

# Emitters intentionally not driven here: {qualname: honest, specific reason}.
# Empty today: every discovered emitter is constructible offline. A future
# emitter needing a live LM / cluster / network goes here with that reason.
_INTENTIONALLY_UNCOVERED: dict[str, str] = {}


# ---------------------------------------------------------------------------
# The court.
# ---------------------------------------------------------------------------


def test_every_discovered_emitter_is_covered_or_allowlisted() -> None:
    discovered = _discover_all_emitters(SRC_ROOT)
    assert discovered, "scan found no emitters at all; the scan itself is broken"
    missing = _unaccounted(set(discovered), set(_COVERED), _INTENTIONALLY_UNCOVERED)
    assert missing == [], f"OCEL emitters neither covered nor allowlisted: {missing}"


def test_no_stale_covered_or_allowlist_entries() -> None:
    discovered = set(_discover_all_emitters(SRC_ROOT))
    assert _stale(discovered, set(_COVERED), _INTENTIONALLY_UNCOVERED) == []
    assert not set(_COVERED) & set(_INTENTIONALLY_UNCOVERED), "entry is both covered and allowed"
    for qualname, reason in _INTENTIONALLY_UNCOVERED.items():
        assert len(reason.strip()) >= 20, f"{qualname}: reason must be specific"


def test_every_covered_entry_names_a_real_test_in_this_module() -> None:
    for qualname, test_name in _COVERED.items():
        assert callable(globals().get(test_name)), f"{qualname} -> missing test {test_name}"


def test_scan_finds_expected_real_emitters_and_excludes_non_emitters() -> None:
    discovered = _discover_all_emitters(SRC_ROOT)
    assert "gymact.ocel.receipts_to_ocel" in discovered
    assert "gymact.policy_ecology_ocel.policy_ecology_events_to_ocel" in discovered
    assert "gymact.ocel.digest_ocel_log" not in discovered  # returns str
    assert "gymact.ocel.validate_ocel_log" not in discovered  # returns None
    assert not any(".explore_" in name for name in discovered)


def test_content_detector_finds_emitters_the_name_rule_misses_and_excludes_non_emitters() -> None:
    by_name = set(_discover_emitters(SRC_ROOT))
    by_content = set(_discover_content_emitters(SRC_ROOT))
    invisible_to_name_rule = {
        "gymact.synthetic_ocel.manufacture_ocel_history",
        "gymact.synthetic_ocel.executed_ocel_result",
        "gymact.synthetic_ocel.observed_ocel_result",
        "gymact.manufacture.manufacture_synthetic_ocel_result",
        "gymact.combinatorial_ocel.run_combinatorial_maximum",
        "gymact.execution_loop.loop_log",
        "gymact.powl.runner.run_pipeline",
        "gymact.powl.ocel_bridge.GymactOcelSessionRecorder.close",
    }
    assert invisible_to_name_rule <= by_content
    assert not invisible_to_name_rule & by_name
    # Precision witnesses: mention OCEL / return dicts but do not emit a log.
    for non_emitter in (
        "gymact.cost_ledger.sum_costs_by_unit",
        "gymact.manufacture.export_manufacturing_bundle",
        "gymact.manufacture.synthetic_ocel_manufacturing_contract",
        "gymact.policy_ecology_ocel._event_attributes",
        "gymact.combinatorial_ocel.drive_combination",
        "gymact.runtime_evolution.ocel.event.Event.receipt",
        "gymact.runtime_evolution.ocel.receipt.Receipt.receipt",
        "gymact.runtime_evolution.ocel.replay.Replay.receipt",
    ):
        assert non_emitter not in by_content, non_emitter
    assert not any(".explore_" in name for name in by_content)


# ---------------------------------------------------------------------------
# Controls / mutation checks (run on tmp trees and corrupted dicts).
# ---------------------------------------------------------------------------


def test_control_fake_emitter_in_tmp_tree_is_reported_unaccounted(tmp_path: Path) -> None:
    pkg = tmp_path / "gymact"
    (pkg / "explore_hidden").mkdir(parents=True)
    (pkg / "explore_hidden" / "mod.py").write_text(
        "def hidden_to_ocel(x) -> dict:\n    return {}\n"
    )
    (pkg / "fake.py").write_text(
        "from typing import Any\n"
        "def rogue_events_to_ocel(events) -> dict[str, Any]:\n    return {}\n"
        "def rogue_ocel_digest_ocel_log(log) -> str:\n    return ''\n"
        "class K:\n    def to_ocel_log(self) -> dict[str, Any]:\n        return {}\n"
        "    def write_ocel_log(self) -> tuple[dict[str, Any], str]:\n        return {}, ''\n"
    )
    discovered = _discover_emitters(pkg)
    assert set(discovered) == {
        "gymact.fake.rogue_events_to_ocel",
        "gymact.fake.K.to_ocel_log",
        "gymact.fake.K.write_ocel_log",
    }
    unaccounted = _unaccounted(set(discovered), set(), {})
    assert "gymact.fake.rogue_events_to_ocel" in unaccounted
    # Allowlisting one removes exactly that one; the rest still fail.
    remaining = _unaccounted(
        set(discovered), set(), {"gymact.fake.rogue_events_to_ocel": "needs a live LM"}
    )
    assert "gymact.fake.rogue_events_to_ocel" not in remaining and len(remaining) == 2


def test_control_content_detector_reports_unusually_named_emitters(tmp_path: Path) -> None:
    pkg = tmp_path / "gymact"
    (pkg / "explore_hidden").mkdir(parents=True)
    (pkg / "explore_hidden" / "mod.py").write_text(
        "def sneaky() -> dict:\n    return {'events': [], 'objects': []}\n"
    )
    (pkg / "fake.py").write_text(
        "from typing import Any\n"
        "from gymact.ocel import validate_ocel_log\n"
        "def assemble_history(x) -> dict[str, Any]:\n"
        "    return {'events': x, 'objects': []}\n"
        "def types_only() -> dict[str, Any]:\n"
        "    return {'eventTypes': [], 'objectTypes': []}\n"
        "def checked(log) -> dict[str, Any]:\n"
        "    validate_ocel_log(log)\n    return log\n"
        "def wrapped() -> 'OCELGymResult':\n    return None\n"
        "class K:\n"
        "    def build(self) -> tuple[dict[str, Any], str]:\n"
        "        return {'events': [], 'objects': []}, ''\n"
        "    def outer(self) -> dict[str, Any]:\n"
        "        def inner() -> dict[str, Any]:\n"
        "            return {'events': [], 'objects': []}\n"
        "        return {}\n"
        "# non-emitters: partial keys, no annotation, non-dict annotation, no signal\n"
        "def only_events() -> dict[str, Any]:\n    return {'events': []}\n"
        "def unannotated():\n    return {'events': [], 'objects': []}\n"
        "def returns_str(log) -> str:\n    validate_ocel_log(log)\n    return ''\n"
        "def ocel_in_docstring() -> dict[str, float]:\n"
        "    'builds an OCEL summary'\n    return {}\n"
    )
    expected = {
        "gymact.fake.assemble_history",
        "gymact.fake.types_only",
        "gymact.fake.checked",
        "gymact.fake.wrapped",
        "gymact.fake.K.build",
    }
    assert set(_discover_content_emitters(pkg)) == expected
    # The name detector alone is blind to all of them (the gap being closed).
    assert _discover_emitters(pkg) == {}
    # The union feeds the court: each is unaccounted until covered/allowlisted.
    union = _discover_all_emitters(pkg)
    assert set(union) == expected
    assert _unaccounted(set(union), set(), {}) == sorted(expected)
    assert _unaccounted(set(union), {"gymact.fake.checked"}, {"gymact.fake.wrapped": "x" * 20}) == [
        "gymact.fake.K.build",
        "gymact.fake.assemble_history",
        "gymact.fake.types_only",
    ]


def test_control_union_keeps_name_detector_results(tmp_path: Path) -> None:
    pkg = tmp_path / "gymact"
    pkg.mkdir()
    (pkg / "fake.py").write_text(
        "def rogue_events_to_ocel(events) -> dict:\n    return {}\n"
        "def rogue_builder() -> dict:\n    return {'events': [], 'objects': []}\n"
    )
    assert set(_discover_all_emitters(pkg)) == {
        "gymact.fake.rogue_events_to_ocel",
        "gymact.fake.rogue_builder",
    }


def test_control_stale_entries_are_detected() -> None:
    discovered = {"a.f"}
    assert _stale(discovered, {"a.f"}, {"a.gone": "reason that is long enough here"}) == ["a.gone"]
    assert _stale(discovered, {"a.removed"}, {}) == ["a.removed"]


def test_control_validate_ocel_log_rejects_corrupted_logs() -> None:
    # Missing object-attribute `time` (the shipped policy-ecology defect).
    good = policy_ecology_events_to_ocel(_policy_events())
    validate_ocel_log(good)
    missing_time = {**good, "objects": [dict(o) for o in good["objects"]]}
    missing_time["objects"][0] = {
        **missing_time["objects"][0],
        "attributes": [{"name": "population_kind", "value": "root"}],
    }
    with pytest.raises(ValidationError):
        validate_ocel_log(missing_time)

    # Non-string event attribute value (the other shipped defect).
    non_string = {**good, "events": [dict(e) for e in good["events"]]}
    non_string["events"][0]["attributes"] = [{"name": "size", "value": 4}]
    with pytest.raises(ValidationError):
        validate_ocel_log(non_string)


def test_covered_qualnames_resolve_to_real_callables() -> None:
    # Guard against a covered entry naming something that cannot be imported.
    for qualname in _COVERED:
        parts = qualname.split(".")
        target: Any = None
        module_len = len(parts) - 1
        while module_len > 0 and target is None:
            try:
                target = importlib.import_module(".".join(parts[:module_len]))
            except ImportError:
                module_len -= 1
        assert target is not None, f"{qualname}: no importable module prefix"
        for attr in parts[module_len:]:
            target = getattr(target, attr)
        assert callable(target), qualname
