"""Chicago-style: a real GymAct episode driven against a real `inspect_ai`
evaluation, backed by Inspect's own real `mockllm` model provider so no paid
API key is required for a deterministic pass.

Target: `~/autofde-lab/vendor/gyms/inspect-evals` is a lazy git submodule
with no checked-out content in this checkout (only the parent directory
exists) -- see `src/gymact/gyms/inspect_evals.py`'s module docstring for the
full explanation, including the real pinned revision in
`~/autofde-lab/docs/papers/gym-lock.ttl`. This test file therefore exercises
the real, installed `inspect-ai` PyPI package directly (verified installable
via `uv pip install inspect-ai` in this session; `inspect_ai.__version__ ==
"0.3.252"`), not a checked-out `inspect_evals` task package.

Per `gymact.standing.require_standing`, the real thing (an importable
`inspect_ai`) is the default; this only degrades to a named, visible skip if
`inspect_ai` genuinely cannot be imported, and only when the run explicitly
opts in via `GYMACT_ALLOW_DEGRADED_STANDINGS=LOCAL_GYM:inspect-evals` (or
`"*"`).
"""

from __future__ import annotations

import importlib.util

import pytest

from gymact.standing import require_standing

require_standing(
    "LOCAL_GYM:inspect-evals",
    available=importlib.util.find_spec("inspect_ai") is not None,
    reason="the 'inspect_ai' package is not importable in this environment",
)

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.inspect_evals import (  # noqa: E402
    INSPECT_SOLVE_SAMPLE_CAPABILITY,
    InspectEvalsProvider,
)
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

SOLVE_SAMPLE = "urn:gymact:inspect-evals:capability:solve_sample"
# inspect_evals.py's requires_authority now defaults to True (a real DO
# capability running a real inspect_ai eval must not run unauthorized) --
# every gym-driven test below explicitly admits AUTHORITY.
AUTHORITY = "urn:test:inspect-evals-authority"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(InspectEvalsProvider())
    return gym

# inspect_ai's own internal anyio.MemoryObjectReceiveStream (allocated deep
# inside inspect_ai._eval.eval_async's own transcript/display plumbing, not
# by anything this module allocates) is sometimes garbage-collected without
# being explicitly closed, which anyio reports as an unraisable
# ResourceWarning at GC time -- outside any exception handler this module's
# own code could catch. Verified in this session: the real eval_async() call
# succeeds and produces a real, correctly scored EvalLog every time; this
# warning fires only during later, unrelated garbage collection. Silencing
# it here (rather than repo-wide) is scoped to this one real, named upstream
# cleanup gap in inspect_ai 0.3.252, not a blanket warnings suppression.
pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")

# `filterwarnings` above only silences a PytestUnraisableExceptionWarning raised
# while *this* module's own tests are running -- pytest's unraisable-exception
# hook attributes a GC-time warning to whichever test happens to be executing
# when Python's collector actually reclaims the leaked object, which for this
# object is nondeterministic and was observed landing on a later, unrelated
# module (test_ocel.py) purely from suite ordering. A bare gc.collect() at this
# module's own teardown does not reliably force reclamation either (verified:
# still reproduces after adding one). See test_ocel.py's matching, cross-
# referenced suppression for the other half of this scoped workaround.


async def _run_real_inspect_episode(*, custom_outputs: list[str]) -> list:
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
                "log_dir": "./.inspect_logs",
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


async def test_real_materialize_builds_a_real_inspect_task_environment() -> None:
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


async def test_solve_sample_capability_really_runs_inspect_eval_and_scores_correct() -> None:
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
                "log_dir": "./.inspect_logs",
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


async def test_solve_sample_capability_really_scores_incorrect_when_the_model_is_wrong() -> None:
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
                "log_dir": "./.inspect_logs",
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


async def test_inspect_evals_episode_replays_conformant_and_produces_a_valid_ocel_log() -> None:
    receipts = await _run_real_inspect_episode(custom_outputs=["4"])
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
