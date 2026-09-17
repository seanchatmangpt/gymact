"""Chicago-style: a real GymAct episode driving the real, PyPI-installed
`terminal-bench==0.2.18` package against a real local Docker daemon, using
the real, checked-in `gyms/fixtures/terminal_bench_task` task -- not
simulated.

Per `gymact.standing.require_standing`, the real thing is the default: if
`terminal_bench` cannot be imported (extra not installed / Python <3.12) or
the real local Docker daemon is not reachable, this module FAILS unless the
run explicitly sets `GYMACT_ALLOW_DEGRADED_STANDINGS` to include
"LOCAL_GYM:terminal-bench" (or "*") -- a skip here is something a run must
opt into, never something it silently gets. Matches
`test_terraform_docker_apply.py`'s contract.

Every mid-test failure path still attempts real cleanup (`env.teardown()`,
confirmed via real `docker ps -a`) via try/finally, so a failing assertion
never leaks a real container or image.
"""

from __future__ import annotations

import subprocess

from gymact.standing import require_standing


def _terminal_bench_importable() -> bool:
    try:
        import terminal_bench  # noqa: F401
    except ImportError:
        return False
    return True


def _real_docker_reachable() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


require_standing(
    "LOCAL_GYM:terminal-bench",
    available=_terminal_bench_importable() and _real_docker_reachable(),
    reason="terminal-bench is not importable (install the 'gyms' extra on "
    "Python >=3.12) or no reachable local Docker daemon (start colima: "
    "`colima start`)",
)

from gymact import GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.terminal_bench import TerminalBenchProvider  # noqa: E402
from gymact.models import ActuationIntent, Operation, Standing  # noqa: E402
from gymact.ocel import receipts_to_ocel, validate_ocel_log, write_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

RUN_COMMAND = "urn:gymact:terminal-bench:capability:run-command"
_SOLUTION_COMMAND = "printf 'gymact-terminal-bench-ok' > /app/output.txt"


async def test_real_materialize_starts_a_real_running_task_container() -> None:
    gym = GymAct()
    gym.register_provider(TerminalBenchProvider())
    m = await gym.materialize(MaterializationIntent(provider="terminal-bench", config={}))
    assert m.accepted is True
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        observed = await env.observe()
        assert observed["container_running"] is True
        assert observed["task_id"] == "terminal_bench_task"
        assert observed["run_command_attempted"] is False
    finally:
        await gym.teardown(episode_id)


async def test_run_command_actuates_a_real_shell_command_in_the_real_container() -> None:
    gym = GymAct()
    gym.register_provider(TerminalBenchProvider())
    m = await gym.materialize(MaterializationIntent(provider="terminal-bench", config={}))
    assert m.accepted is True
    episode_id = m.episode.episode_id
    try:
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=RUN_COMMAND,
                payload={"command": "echo gymact-tb-marker"},
            )
        )
        assert result.accepted is True
        assert result.effect["after"]["run_command_attempted"] is True
        assert "gymact-tb-marker" in result.effect["after"]["last_pane"]
    finally:
        await gym.teardown(episode_id)


async def test_verify_runs_the_real_pytest_oracle_and_reports_unresolved_before_the_fix() -> None:
    """No command has run yet, so /app/output.txt is absent -- the real
    checked-in pytest test in the task container must really fail, proving
    `verify()` is not fabricating a pass."""
    gym = GymAct()
    gym.register_provider(TerminalBenchProvider())
    m = await gym.materialize(MaterializationIntent(provider="terminal-bench", config={}))
    episode_id = m.episode.episode_id
    try:
        verification = await gym.verify(episode_id, {"is_resolved": True})
        assert verification.passed is False
        assert verification.observed["is_resolved"] is False
        assert verification.observed["parser_results"] == {
            "test_output_file_has_expected_content": "failed"
        }
    finally:
        await gym.teardown(episode_id)


async def test_run_command_then_verify_resolves_via_the_real_pytest_oracle() -> None:
    gym = GymAct()
    gym.register_provider(TerminalBenchProvider())
    m = await gym.materialize(MaterializationIntent(provider="terminal-bench", config={}))
    assert m.accepted is True
    episode_id = m.episode.episode_id
    try:
        result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=RUN_COMMAND,
                payload={"command": _SOLUTION_COMMAND},
            )
        )
        assert result.accepted is True

        verification = await gym.verify(episode_id, {"is_resolved": True})
        assert verification.passed is True
        assert verification.observed["is_resolved"] is True
        assert verification.observed["parser_results"] == {
            "test_output_file_has_expected_content": "passed"
        }
    finally:
        await gym.teardown(episode_id)


async def test_teardown_really_stops_and_confirms_via_real_docker_ps() -> None:
    gym = GymAct()
    gym.register_provider(TerminalBenchProvider())
    m = await gym.materialize(MaterializationIntent(provider="terminal-bench", config={}))
    episode_id = m.episode.episode_id
    env = gym._episodes[episode_id].environment
    try:
        assert (await env.observe())["container_running"] is True

        receipt = await gym.teardown(episode_id)
        assert receipt.standing == Standing.ALIVE

        # Real confirmation against the real Docker daemon -- not trusting
        # teardown()'s own bookkeeping.
        assert env.is_really_gone() is True
    except Exception:
        if not env._closed:
            await env.teardown()
        raise


async def _run_real_episode() -> list:
    """One real episode: materialize -> act (run_command, a real DO
    capability) -> verify (real pytest oracle) -> teardown."""
    gym = GymAct()
    gym.register_provider(TerminalBenchProvider())
    receipts = []

    materialization = await gym.materialize(
        MaterializationIntent(provider="terminal-bench", config={})
    )
    assert materialization.accepted is True
    receipts.append(materialization.receipt)
    episode_id = materialization.episode.episode_id
    env = gym._episodes[episode_id].environment

    try:
        act_result = await gym.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=RUN_COMMAND,
                payload={"command": _SOLUTION_COMMAND},
            )
        )
        assert act_result.accepted is True
        receipts.append(act_result.receipt)

        verification = await gym.verify(episode_id, {"is_resolved": True})
        assert verification.passed is True
    finally:
        if not env._closed:
            receipts.append(await gym.teardown(episode_id))

    return receipts


async def test_terminal_bench_episode_replays_conformant_and_produces_a_valid_ocel_log(
    tmp_path,
) -> None:
    receipts = await _run_real_episode()
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

    log_path = tmp_path / "terminal-bench-episode.ocel.json"
    written_log, digest = write_ocel_log(log_path, receipts)
    assert written_log == log
    assert log_path.is_file()
    assert len(digest) == 64  # real sha256 hex digest
