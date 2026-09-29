"""Chicago-style: a real GymAct episode driven against a real `inspect_ai`
evaluation, backed by Inspect's own real `mockllm` model provider so no paid
API key is required for a deterministic pass.

Target: `~/autofde-lab/vendor/gyms/inspect-evals` is a lazy git submodule
with no checked-out content in this checkout (only the parent directory
exists) -- see `src/gymact/gyms/inspect_evals.py`'s module docstring for the
full explanation, including the real pinned revision in
`~/autofde-lab/docs/papers/gym-lock.ttl`. This test file therefore exercises
the real, installed `inspect-ai` PyPI package directly, not a checked-out
`inspect_evals` task package.

Per `gymact.standing.require_standing`, the real thing (an importable
`inspect_ai`) is the default; this only degrades to a named, visible skip if
`inspect_ai` genuinely cannot be imported, and only when the run explicitly
opts in via `GYMACT_ALLOW_DEGRADED_STANDINGS=LOCAL_GYM:inspect-evals` (or
`"*"`).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from gymact.standing import named_standing_skip

named_standing_skip(
    "LOCAL_GYM:inspect-evals",
    available=importlib.util.find_spec("inspect_ai") is not None,
    reason="the 'inspect_ai' package is not importable in this environment",
)

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.gyms.inspect_evals import (
    INSPECT_SOLVE_SAMPLE_CAPABILITY,
    InspectEvalsProvider,
)
from gymact.models import ActuationIntent, Operation, Standing
from gymact.ocel import receipts_to_ocel, validate_ocel_log
from gymact.process import ConformanceChecker

SOLVE_SAMPLE = "urn:gymact:inspect-evals:capability:solve_sample"
# inspect_evals.py's requires_authority now defaults to True (a real DO
# capability running a real inspect_ai eval must not run unauthorized) --
# every gym-driven test below explicitly admits AUTHORITY.
AUTHORITY = "urn:test:inspect-evals-authority"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(InspectEvalsProvider())
    return gym


async def _run_real_inspect_episode(*, custom_outputs: list[str], log_dir: str) -> list:
    gym = _authorized_gym()
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="inspect-evals",
            config={
                "input": "What is 2 + 2? Answer with just the number.",
                "target": "4",
                "model": "mockllm/model",
                "model_args": {"custom_outputs": custom_outputs},
                "log_dir": log_dir,
            },
        )
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id

    receipts.append(
        (
            await gym.act(
                ActuationIntent(
                    episode_id=episode_id, capability=SOLVE_SAMPLE, authority_ref=AUTHORITY
                )
            )
        ).receipt
    )

    receipts.append(await gym.teardown(episode_id, authority_ref=AUTHORITY))
    return receipts


async def test_real_materialize_builds_a_real_inspect_task_environment(tmp_path) -> None:
    gym = GymAct()
    gym.register_provider(InspectEvalsProvider())

    materialization = await gym.materialize(
        MaterializationIntent(provider="inspect-evals", config={})
    )
    assert materialization.accepted is True
    episode_id = materialization.episode.episode_id

    # Nothing has been solved yet -- observe() reflects the real,
    # not-yet-attempted initial state, not a canned "solved" placeholder.
    state = materialization.observation.state
    assert state["attempted"] is False
    assert state["solved"] is False

    await gym.teardown(episode_id)


async def test_solve_sample_capability_really_runs_inspect_eval_and_scores_correct(
    tmp_path,
) -> None:
    """Inspect's real mockllm provider replays the literal completion "4";
    Inspect's real match() scorer really compares it against the real
    target "4" -- this is a real CORRECT verdict from Inspect's own scoring
    code, not a fabricated pass."""
    gym = _authorized_gym()

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="inspect-evals",
            config={
                "input": "What is 2 + 2? Answer with just the number.",
                "target": "4",
                "model": "mockllm/model",
                "model_args": {"custom_outputs": ["4"]},
                "log_dir": str(tmp_path / "inspect_logs"),
            },
        )
    )
    episode_id = materialization.episode.episode_id

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=SOLVE_SAMPLE, authority_ref=AUTHORITY)
    )
    assert result.accepted is True
    after = result.effect["after"]
    assert after["attempted"] is True
    assert after["status"] == "success"
    assert after["solved"] is True
    assert after["score_answer"] == "4"

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_solve_sample_capability_really_scores_incorrect_when_the_model_is_wrong(
    tmp_path,
) -> None:
    """The negative case: Inspect's real match() scorer really marks a wrong
    completion INCORRECT -- proves this provider surfaces Inspect's genuine
    verdict rather than always reporting success."""
    gym = _authorized_gym()

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="inspect-evals",
            config={
                "input": "What is 2 + 2? Answer with just the number.",
                "target": "4",
                "model": "mockllm/model",
                "model_args": {"custom_outputs": ["not a number"]},
                "log_dir": str(tmp_path / "inspect_logs"),
            },
        )
    )
    episode_id = materialization.episode.episode_id

    result = await gym.act(
        ActuationIntent(episode_id=episode_id, capability=SOLVE_SAMPLE, authority_ref=AUTHORITY)
    )
    assert result.accepted is True
    after = result.effect["after"]
    assert after["attempted"] is True
    assert after["solved"] is False
    assert after["score_value"] == "I"

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


async def test_capabilities_exposes_the_real_solve_sample_do_capability() -> None:
    provider = InspectEvalsProvider()
    env = await provider.materialize(scenario=None, config={})
    assert env.capabilities() == (INSPECT_SOLVE_SAMPLE_CAPABILITY,)
    await env.teardown()


async def test_actuate_rejects_an_unsupported_capability_binding() -> None:
    provider = InspectEvalsProvider()
    env = await provider.materialize(scenario=None, config={})
    bogus = INSPECT_SOLVE_SAMPLE_CAPABILITY.model_copy(update={"binding": "not_a_real_binding"})
    try:
        await env.actuate(bogus, {})
        raised = False
    except ValueError:
        raised = True
    assert raised is True
    await env.teardown()


async def test_checkpoint_and_restore_really_round_trip_the_last_real_result() -> None:
    provider = InspectEvalsProvider()
    env = await provider.materialize(
        scenario=None,
        config={"model_args": {"custom_outputs": ["4"]}},
    )
    await env.actuate(INSPECT_SOLVE_SAMPLE_CAPABILITY, {})
    solved_checkpoint = await env.checkpoint()
    assert solved_checkpoint["solved"] is True

    # Restore back to the never-attempted state (env's own __init__ default)
    # and confirm observe() really reflects the restored state, not the
    # post-actuation one.
    never_attempted = {
        "attempted": False,
        "status": None,
        "score_value": None,
        "score_answer": None,
        "solved": False,
    }
    await env.restore(never_attempted)
    assert await env.observe() == never_attempted

    await env.restore(solved_checkpoint)
    assert await env.observe() == solved_checkpoint
    await env.teardown()


async def test_verify_passes_when_observed_state_matches_expected_subset() -> None:
    provider = InspectEvalsProvider()
    env = await provider.materialize(
        scenario=None,
        config={"model_args": {"custom_outputs": ["4"]}},
    )
    await env.actuate(INSPECT_SOLVE_SAMPLE_CAPABILITY, {})

    passed, observed = await env.verify({"solved": True})
    assert passed is True
    assert observed["solved"] is True

    failed, _ = await env.verify({"solved": False})
    assert failed is False
    await env.teardown()


async def test_environment_methods_refuse_use_after_teardown() -> None:
    provider = InspectEvalsProvider()
    env = await provider.materialize(scenario=None, config={})
    await env.teardown()
    try:
        await env.observe()
        raised = False
    except RuntimeError:
        raised = True
    assert raised is True


async def test_materialize_rejects_non_string_input() -> None:
    provider = InspectEvalsProvider()
    try:
        await provider.materialize(scenario=None, config={"input": 5})
        raised = False
    except TypeError:
        raised = True
    assert raised is True


async def test_materialize_rejects_non_string_target() -> None:
    provider = InspectEvalsProvider()
    try:
        await provider.materialize(scenario=None, config={"target": ""})
        raised = False
    except TypeError:
        raised = True
    assert raised is True


async def test_materialize_rejects_non_string_model() -> None:
    provider = InspectEvalsProvider()
    try:
        await provider.materialize(scenario=None, config={"model": 7})
        raised = False
    except TypeError:
        raised = True
    assert raised is True


async def test_materialize_rejects_non_dict_model_args() -> None:
    provider = InspectEvalsProvider()
    try:
        await provider.materialize(scenario=None, config={"model_args": "nope"})
        raised = False
    except TypeError:
        raised = True
    assert raised is True


async def test_materialize_rejects_non_string_log_dir() -> None:
    provider = InspectEvalsProvider()
    try:
        await provider.materialize(scenario=None, config={"log_dir": ""})
        raised = False
    except TypeError:
        raised = True
    assert raised is True


async def test_materialize_rejects_non_boolean_requires_authority() -> None:
    provider = InspectEvalsProvider()
    try:
        await provider.materialize(scenario=None, config={"requires_authority": "yes"})
        raised = False
    except TypeError:
        raised = True
    assert raised is True


async def test_inspect_evals_episode_replays_conformant_and_produces_a_valid_ocel_log(
    tmp_path,
) -> None:
    receipts = await _run_real_inspect_episode(
        custom_outputs=["4"], log_dir=str(tmp_path / "inspect_logs")
    )
    operations = [r.operation for r in receipts]

    assert operations == [
        Operation.MATERIALIZE,
        Operation.ACT,
        Operation.TEARDOWN,
    ]

    result = ConformanceChecker().check(operations)
    assert result.conformant is True

    log = receipts_to_ocel(receipts)
    validate_ocel_log(log)  # real jsonschema.validate against real OCEL 2.0 schema

    teardown_receipt = receipts[-1]
    assert teardown_receipt.standing == Standing.ALIVE


def test_real_solve_does_not_install_the_process_global_nest_asyncio_patch(tmp_path) -> None:
    """Inspect's `init_nest_asyncio()` permanently patches `asyncio.run` for the
    whole process with a variant that never closes the loop it creates; those
    loops (and their AF_UNIX self-pipes) are then finalized by the GC during
    unrelated later tests, failing them under warnings-as-errors. A real solve
    through this adapter must leave the process's asyncio unpatched.

    Runs in a fresh interpreter: the patch is one-way and process-global, so an
    in-process check would be order-dependent on whichever earlier test first
    tripped it."""
    script = (
        "import asyncio, sys\n"
        "sys.path.insert(0, sys.argv[2])\n"
        "from test_inspect_evals import _run_real_inspect_episode\n"
        "assert not hasattr(asyncio, '_nest_patched')\n"
        "receipts = asyncio.run(_run_real_inspect_episode(\n"
        "    custom_outputs=['4'], log_dir=sys.argv[1]))\n"
        "print('RECEIPTS', len(receipts))\n"
        "print('NEST_PATCHED', hasattr(asyncio, '_nest_patched'))\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "inspect_logs"), str(Path(__file__).parent)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert "RECEIPTS 3" in done.stdout
    assert "NEST_PATCHED False" in done.stdout


# --- Contract tests for the private Inspect symbol `_run_inspect_eval` relies on ---
#
# `_run_inspect_eval` holds `inspect_ai._util._async._initialised_nest_asyncio`
# True (guarded by `hasattr`) so `init_nest_asyncio()` short-circuits instead of
# installing `nest_asyncio2`'s one-way, process-global `asyncio.run` patch. That
# flag is private: if Inspect renames it, the `hasattr` guard silently turns the
# flag half of the fix into a no-op. These tests fail loudly on that drift.
# Verified against inspect_ai 0.3.272, where `init_nest_asyncio()` is
#   `if not _initialised_nest_asyncio: nest_asyncio.apply(); flag = True`.
# Each behavioral probe runs in a fresh interpreter because the patch is one-way.


def _run_fresh_python(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script, *args],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_inspect_private_nest_flag_exists_and_is_bool() -> None:
    from inspect_ai._util import _async as inspect_async

    assert hasattr(inspect_async, "_initialised_nest_asyncio"), (
        "inspect_ai renamed/removed _initialised_nest_asyncio: the flag half of "
        "_run_inspect_eval's nest_asyncio guard is now a silent no-op"
    )
    assert isinstance(inspect_async._initialised_nest_asyncio, bool)
    assert callable(inspect_async.init_nest_asyncio)


def test_inspect_init_nest_asyncio_consults_the_flag() -> None:
    script = (
        "import asyncio\n"
        "from inspect_ai._util import _async as m\n"
        "assert not hasattr(asyncio, '_nest_patched')\n"
        "m._initialised_nest_asyncio = True\n"
        "m.init_nest_asyncio()\n"
        "print('AFTER_FLAG_TRUE', hasattr(asyncio, '_nest_patched'))\n"
    )
    control = (
        "import asyncio\n"
        "from inspect_ai._util import _async as m\n"
        "m._initialised_nest_asyncio = False\n"
        "m.init_nest_asyncio()\n"
        "print('AFTER_FLAG_FALSE', hasattr(asyncio, '_nest_patched'))\n"
        "print('FLAG_NOW', m._initialised_nest_asyncio)\n"
    )
    held = _run_fresh_python(script)
    assert held.returncode == 0, held.stderr
    assert "AFTER_FLAG_TRUE False" in held.stdout

    # Control: proves the probe can see the patch, so the line above is not vacuous.
    released = _run_fresh_python(control)
    assert released.returncode == 0, released.stderr
    assert "AFTER_FLAG_FALSE True" in released.stdout
    assert "FLAG_NOW True" in released.stdout


def test_run_inspect_eval_flag_blocks_reentrant_patch_from_inside_eval(tmp_path) -> None:
    """Independent need for the flag half: user code running inside `eval()`'s
    own event loop that calls a sync Inspect API (here `read_eval_log`, which goes
    through `run_coroutine` -> `init_nest_asyncio`) would install the process-global
    patch. With the flag held, the patch is not installed (the re-entrant call
    fails loudly instead). Inspect's own default eval path never does this, so
    this only covers caller-supplied solver/scorer/hook code."""
    script = (
        "import asyncio, glob, sys\n"
        "from inspect_ai import Task, eval as inspect_eval\n"
        "from inspect_ai.dataset import Sample\n"
        "from inspect_ai.log import read_eval_log\n"
        "from inspect_ai.model import ModelOutput\n"
        "from inspect_ai.scorer import match\n"
        "from inspect_ai.solver import generate, solver\n"
        "from gymact.gyms.inspect_evals import _run_inspect_eval\n"
        "log_dir = sys.argv[1]\n"
        "out = ModelOutput.from_content('mockllm/model', '4')\n"
        "args = dict(model='mockllm/model', model_args={'custom_outputs': [out]})\n"
        "inspect_eval(Task(dataset=[Sample(input='q', target='4')], solver=[generate()],\n"
        "                  scorer=match()), log_dir=log_dir, display='none', **args)\n"
        "assert not hasattr(asyncio, '_nest_patched')\n"
        "path = glob.glob(log_dir + '/*.eval')[0]\n"
        "@solver\n"
        "def reads_log_synchronously():\n"
        "    async def run(state, generate):\n"
        "        read_eval_log(path, header_only=True)\n"
        "        return state\n"
        "    return run\n"
        "task = Task(dataset=[Sample(input='q', target='4')],\n"
        "            solver=[reads_log_synchronously(), generate()], scorer=match())\n"
        "logs = _run_inspect_eval(task=task, log_dir=log_dir, **args)\n"
        "print('STATUS', logs[0].status)\n"
        "print('NEST_PATCHED', hasattr(asyncio, '_nest_patched'))\n"
    )
    done = _run_fresh_python(script, str(tmp_path / "inspect_logs"))

    assert done.returncode == 0, done.stderr
    assert "NEST_PATCHED False" in done.stdout
