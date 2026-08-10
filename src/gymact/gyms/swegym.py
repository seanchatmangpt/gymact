"""First-class GymAct provider for the real upstream SWE-Gym benchmark.

This integration deliberately wraps SWE-Gym's own held-out test suites instead of
reimplementing test authoring: the ``FAIL_TO_PASS``/``PASS_TO_PASS`` test directives
that define whether a candidate patch resolves an issue are the upstream dataset's own
fields, and grading them is nothing more than running the tests SWE-Gym itself ships
and reading their real pass/fail outcome. GymAct owns the actuation boundary around
that grading (authority, admission, receipts, replay) — it never re-derives what
counts as "solved."

Upstream compatibility baseline:
    dataset  SWE-Gym/SWE-Gym (HuggingFace, ``train`` split)
    images   xingyaoww/sweb.eval.x86_64.<instance_id with '__' -> '_s_'>, lowercased

Unlike SREGym (see ``gymact.gyms.sregym``), the admitted compatibility subject here is
not a pinned git checkout of an upstream harness — SWE-Gym ships no runnable harness
repository GymAct launches a subprocess against. The subject is a HuggingFace dataset
revision: one row of ``SWE-Gym/SWE-Gym`` (or a caller-supplied dataset override, e.g.
``SWE-Gym/SWE-Gym-Lite``) identified by its own ``instance_id``, plus the upstream
prebuilt Docker image published for that instance. There is no "checkout" to pin a git
HEAD against; the dataset row itself, fetched live via the ``datasets`` library, is the
admitted upstream artifact. This is a deliberate, named difference from sregym.py's
``SREGYM_ROOT``/``_git_head`` revision pinning, not an oversight.

Consequence law is preserved: a container that starts and a test command that exits is
not a solved benchmark. ``resolved`` is derived only from the real, independently run
FAIL_TO_PASS and PASS_TO_PASS test suites, using the same baseline-subtract semantics
as upstream ``swegym_cube.task.SWEGymTask.evaluate``: PASS_TO_PASS tests are run once
BEFORE any patch is applied to establish which of them are already broken in the
unpatched image, and a PASS_TO_PASS test that was already failing pre-patch is never
counted as a candidate-patch regression. The environment requires authority for every
run because it mutates a live Docker world (pulls an image, starts a container, applies
patches, executes test suites, tears the container down).

Non-root writability gap (see upstream ``swegym_cube.task.SWEGymTask._make_tool`` /
``_raise_if_unpatchable``): some SWE-Gym images ship root-owned package subdirectories
that a non-root container user cannot make writable. GymAct applies the same
git-safe-directory + copy/move writability normalisation upstream applies, then probes
writability directly rather than silently attempting a patch that would fail with
"Permission denied" and be misread as a candidate-patch defect. An unpatchable
container is a typed refusal (``SWEGYM_CONTAINER_UNPATCHABLE_NON_ROOT``), never a
silent ``resolved=False``.
"""

from __future__ import annotations

import base64
import json
import re
import shlex
import shutil
from copy import deepcopy
from dataclasses import dataclass
from subprocess import PIPE
from typing import Any
from uuid import uuid4

import anyio

from gymact.models import Capability, Consequence

SWEGYM_UPSTREAM_DATASET = "SWE-Gym/SWE-Gym"
SWEGYM_UPSTREAM_SPLIT = "train"

SWEGYM_EVALUATE_CAPABILITY = Capability(
    iri="urn:gymact:swegym:capability:evaluate-patch",
    title=(
        "Apply a candidate patch to an admitted SWE-Gym task and independently grade "
        "it via the task's own held-out fail_to_pass/pass_to_pass tests"
    ),
    consequence=Consequence.DO,
    binding="evaluate-patch",
)

_REQUIRED_BINARIES = ("docker", "git")

_WORKDIR = "/testbed"

_CONDA_ACTIVATE = (
    "if [ -f /opt/miniconda3/etc/profile.d/conda.sh ]; then "
    ". /opt/miniconda3/etc/profile.d/conda.sh && conda activate testbed; fi"
)

# Docker-level infra failures (container crashed/exited/never started) surface through
# `docker exec`'s own stderr, not through the exit code of whatever was running inside
# the container. An exit code alone cannot distinguish "the test suite failed" from
# "the container was gone" — both look like a non-zero returncode. Matching on these
# daemon-level signatures keeps that distinction real instead of collapsing it into a
# graded loss.
_INFRA_FAILURE_SIGNATURES = (
    "Error response from daemon",
    "OCI runtime exec failed",
    "No such container",
    "is not running",
)

_IMAGE_PULL_TIMEOUT_SECONDS = 1800
_CONTAINER_START_TIMEOUT_SECONDS = 120
_CONTAINER_STOP_TIMEOUT_SECONDS = 120
_WRITABILITY_PROBE_TIMEOUT_SECONDS = 60
_WRITABILITY_WORKAROUND_TIMEOUT_SECONDS = 120
_PATCH_WRITE_TIMEOUT_SECONDS = 60
_PATCH_APPLY_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class _ExecResult:
    """Minimal stand-in for anyio's process result, also used for a timeout outcome."""

    returncode: int
    stdout: bytes
    stderr: bytes


def _image_for_instance(task_id: str) -> str:
    """Reproduce Harbor's ``xingyaoww/sweb.eval.x86_64.*`` naming exactly.

    ``instance_id`` like ``conan-io__conan-14760`` becomes
    ``xingyaoww/sweb.eval.x86_64.conan-io_s_conan-14760`` (lowercased; Docker
    repository names must be lowercase). See
    ``harbor/adapters/swegym/utils.py::get_image_names``.
    """
    modified = task_id.replace("__", "_s_")
    return f"xingyaoww/sweb.eval.x86_64.{modified}".lower()


def _build_test_cmd(test_directives: list[str]) -> str:
    """Build the pytest invocation SWE-Gym's own harness uses for every repo.

    ``-rA`` forces pytest's own "short test summary info" section to print a
    ``FAILED <nodeid>`` line for every failing test, regardless of the run's overall
    result -- required so ``_parse_failed_node_ids`` can compare PASS_TO_PASS failures
    by test identity (baseline vs. post-patch), not just by aggregate exit code. Without
    this, a batched multi-test pytest invocation only reports pass/fail as a whole, and a
    baseline-subtract "was this SPECIFIC test already broken" comparison is impossible --
    the exact real bug this flag closes.
    ``-p no:cacheprovider`` avoids writing to a possibly read-only package root.
    ``-p no:snail`` disables a bundled plugin whose teardown hook raises on some
    images even when every test passed (see upstream ``swegym_cube.task``).
    """
    tests = " ".join(shlex.quote(directive) for directive in test_directives)
    return f"python -m pytest -rA -p no:cacheprovider -p no:snail {tests}"


_FAILED_NODE_ID_RE = re.compile(r"^FAILED\s+(\S+)", re.MULTILINE)


def _parse_failed_node_ids(output: str) -> frozenset[str]:
    """Extract the real per-test node ids pytest's own summary marked FAILED.

    Reads pytest's "short test summary info" section (``-rA``), which prints one
    ``FAILED <nodeid>[ - <reason>]`` line per failing test -- the only place a batched
    pytest invocation exposes per-test identity rather than an aggregate exit code.
    """
    return frozenset(match.group(1) for match in _FAILED_NODE_ID_RE.finditer(output))


class SWEGymEnvironment:
    """One admitted SWE-Gym task, evaluated against its own upstream image."""

    def __init__(
        self,
        *,
        task_id: str,
        repo: str,
        base_commit: str,
        image: str,
        test_patch: str,
        fail_to_pass: list[str],
        pass_to_pass: list[str],
        eval_timeout: int,
    ) -> None:
        self.environment_id = f"urn:gymact:swegym:environment:{uuid4().hex}"
        self.requires_authority = True
        self._task_id = task_id
        self._repo = repo
        self._base_commit = base_commit
        self._image = image
        self._test_patch = test_patch
        self._fail_to_pass = list(fail_to_pass)
        self._pass_to_pass = list(pass_to_pass)
        self._eval_timeout = eval_timeout
        self._closed = False
        self._state: dict[str, Any] = {
            "task_id": task_id,
            "repo": repo,
            "base_commit": base_commit,
            "image": image,
            "fail_to_pass": list(fail_to_pass),
            "pass_to_pass": list(pass_to_pass),
            "attempted": False,
            "resolved": False,
            "container_writable": None,
            "test_patch_apply_tier": None,
            "candidate_patch_apply_tier": None,
            "baseline_pass_to_pass_failures": None,
            "fail_to_pass_results": None,
            "pass_to_pass_results": None,
            "stdout_tail": None,
            "stderr_tail": None,
        }

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return (SWEGYM_EVALUATE_CAPABILITY,)

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return deepcopy(self._state)

    # ── Docker-level primitives ────────────────────────────────────

    @staticmethod
    async def _docker_exec(
        task_id: str, container: str, command: str, *, timeout: int
    ) -> _ExecResult:
        try:
            with anyio.fail_after(timeout):
                result = await anyio.run_process(
                    ["docker", "exec", container, "bash", "-lc", command],
                    stdout=PIPE,
                    stderr=PIPE,
                    check=False,
                )
        except TimeoutError:
            return _ExecResult(returncode=124, stdout=b"", stderr=b"[timed out]")
        stderr_text = result.stderr.decode(errors="replace")
        if result.returncode != 0 and any(
            signature in stderr_text for signature in _INFRA_FAILURE_SIGNATURES
        ):
            raise RuntimeError(f"SWEGYM_CONTAINER_EXEC_FAILED:{task_id}")
        return _ExecResult(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)

    @staticmethod
    async def _apply_patch(task_id: str, container: str, patch: str) -> str | None:
        """Apply ``patch`` via the real 3-tier fallback; return which tier succeeded.

        Mirrors upstream ``swegym_cube.task.SWEGymTask._apply_patch`` exactly: try
        ``git apply``, then ``git apply --reject``, then ``patch --forward`` (which
        does not reverse content the test_patch and an agent's own patch both already
        added). Returns ``None`` — not a raise — when every tier fails: a patch that
        does not apply is graded through the resulting test failures, not treated as
        infra breakage.
        """
        encoded = base64.b64encode(patch.encode()).decode()
        write_result = await SWEGymEnvironment._docker_exec(
            task_id,
            container,
            f"echo '{encoded}' | base64 -d > /tmp/patch.diff",
            timeout=_PATCH_WRITE_TIMEOUT_SECONDS,
        )
        if write_result.returncode != 0:
            raise RuntimeError(f"SWEGYM_PATCH_WRITE_FAILED:{task_id}")

        tier1 = await SWEGymEnvironment._docker_exec(
            task_id,
            container,
            f"cd {_WORKDIR} && git apply /tmp/patch.diff",
            timeout=_PATCH_APPLY_TIMEOUT_SECONDS,
        )
        if tier1.returncode == 0:
            return "git-apply"

        tier2 = await SWEGymEnvironment._docker_exec(
            task_id,
            container,
            f"cd {_WORKDIR} && git apply --reject /tmp/patch.diff",
            timeout=_PATCH_APPLY_TIMEOUT_SECONDS,
        )
        if tier2.returncode == 0:
            return "git-apply-reject"

        tier3 = await SWEGymEnvironment._docker_exec(
            task_id,
            container,
            f"cd {_WORKDIR} && patch --batch --forward --fuzz=5 -p1 -i /tmp/patch.diff",
            timeout=_PATCH_APPLY_TIMEOUT_SECONDS,
        )
        if tier3.returncode == 0:
            return "patch-forward"

        return None

    @staticmethod
    async def _run_tests(
        task_id: str,
        container: str,
        test_directives: list[str],
        *,
        timeout: int,
        strict: bool = True,
    ) -> tuple[bool, str, frozenset[str]]:
        """Run test directives; return (all_passed, last-200-lines-of-output, failed_node_ids).

        Reproduces upstream ``swegym_cube.task.SWEGymTask._run_tests`` exactly,
        including its ``strict=False`` relaxations for PASS_TO_PASS checks (pytest
        exit 4 == no tests collected on a malformed/truncated upstream test id; a
        non-zero exit with zero reported failures on some images' noisy teardown).

        ``failed_node_ids`` is the real per-test breakdown parsed from pytest's own
        ``-rA`` summary (see ``_parse_failed_node_ids``) -- required by the caller's
        baseline-subtract comparison, which must forgive only PASS_TO_PASS tests that
        were ALREADY failing pre-patch, never a genuinely new regression the candidate
        patch introduced in a different, previously-passing test. It is empty whenever
        the aggregate short-circuits report no observed per-test failures (timeout,
        no-tests-collected, or a fully-passing run).
        """
        if not test_directives:
            return True, "", frozenset()
        test_cmd = f"{_CONDA_ACTIVATE} && cd {_WORKDIR} && {_build_test_cmd(test_directives)}"
        result = await SWEGymEnvironment._docker_exec(task_id, container, test_cmd, timeout=timeout)
        raw = result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")
        output = "\n".join(raw.splitlines()[-200:])
        # Parsed from the FULL raw output (not the last-200-lines tail kept for display),
        # since the "short test summary info" section pytest's -rA prints can scroll past
        # the 200-line tail on a large PASS_TO_PASS suite.
        failed_node_ids = _parse_failed_node_ids(raw)

        if result.returncode == 124:
            return False, output + "\n[timed out]", failed_node_ids
        if result.returncode == 4 and not strict:
            return True, output, frozenset()
        if result.returncode == 4 and strict:
            joined = "\n".join(test_directives)
            if re.search(r"\[\s*[^\]]*$", joined, re.MULTILINE):
                return True, output, frozenset()
        if result.returncode != 0 and not strict:
            tests_ran = bool(re.search(r"\b\d+\s+passed\b", output, re.IGNORECASE))
            no_failures = not bool(re.search(r"\b\d+\s+failed\b", output, re.IGNORECASE))
            if tests_ran and no_failures:
                return True, output, frozenset()
        return result.returncode == 0, output, failed_node_ids

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        if capability.binding != "evaluate-patch":
            raise ValueError(f"unsupported swegym binding: {capability.binding}")
        if not isinstance(payload, dict) or "patch" not in payload:
            raise ValueError("SWEGYM_EVALUATE_PAYLOAD_MISSING_PATCH")
        patch = payload["patch"]
        if not isinstance(patch, str):
            raise TypeError("payload.patch must be a string")

        before = deepcopy(self._state)
        self._state["attempted"] = True
        task_id = self._task_id

        try:
            with anyio.fail_after(_IMAGE_PULL_TIMEOUT_SECONDS):
                pull_result = await anyio.run_process(
                    ["docker", "pull", self._image], stdout=PIPE, stderr=PIPE, check=False
                )
        except TimeoutError as exc:
            raise RuntimeError(f"SWEGYM_IMAGE_UNAVAILABLE:{task_id}") from exc
        if pull_result.returncode != 0:
            self._state["stderr_tail"] = pull_result.stderr.decode(errors="replace")[-4000:]
            raise RuntimeError(f"SWEGYM_IMAGE_UNAVAILABLE:{task_id}")

        # container_name is assigned before the try/finally, and the container-creating
        # `docker run` call itself lives INSIDE that try/finally rather than before it.
        # Docker can create a container object and then fail the OCI-runtime "start"
        # phase (a real, reproduced failure mode: nonzero returncode with the container
        # already present in `docker ps -a`, status "Created") -- if the start failure
        # raised before the finally's `docker rm -f` was reachable, that container would
        # leak. `docker rm -f` on a name Docker never created at all is a safe, harmless
        # no-op (`check=False`, exit code discarded), so unconditionally attempting it in
        # finally is correct for every path: never-created, created-but-failed-to-start,
        # and successfully-started-and-torn-down.
        container_name = f"gymact-swegym-{uuid4().hex[:12]}"
        try:
            try:
                with anyio.fail_after(_CONTAINER_START_TIMEOUT_SECONDS):
                    run_result = await anyio.run_process(
                        [
                            "docker",
                            "run",
                            "-d",
                            "--name",
                            container_name,
                            self._image,
                            "sleep",
                            "infinity",
                        ],
                        stdout=PIPE,
                        stderr=PIPE,
                        check=False,
                    )
            except TimeoutError as exc:
                raise RuntimeError(f"SWEGYM_CONTAINER_START_FAILED:{task_id}") from exc
            if run_result.returncode != 0:
                self._state["stderr_tail"] = run_result.stderr.decode(errors="replace")[-4000:]
                raise RuntimeError(f"SWEGYM_CONTAINER_START_FAILED:{task_id}")

            # Non-root writability workaround (mirrors upstream _make_tool exactly):
            # trust the git checkout as safe, then reparent any root-owned .py file
            # ownership to the runtime user via cp+mv before touching anything else.
            await self._docker_exec(
                task_id,
                container_name,
                f"git config --global --add safe.directory {_WORKDIR}",
                timeout=_WRITABILITY_PROBE_TIMEOUT_SECONDS,
            )
            await self._docker_exec(
                task_id,
                container_name,
                f"find {_WORKDIR} -not -path '*/.git/*' -name '*.py' ! -writable "
                f'-exec sh -c \'cp "$1" "$1.tmp" && mv "$1.tmp" "$1"\' _ {{}} \\; '
                f"2>/dev/null || true",
                timeout=_WRITABILITY_WORKAROUND_TIMEOUT_SECONDS,
            )
            probe = await self._docker_exec(
                task_id,
                container_name,
                f"test -w {_WORKDIR} && echo WRITABLE || echo READONLY",
                timeout=_WRITABILITY_PROBE_TIMEOUT_SECONDS,
            )
            writable = "WRITABLE" in probe.stdout.decode(errors="replace")
            self._state["container_writable"] = writable
            if not writable:
                raise RuntimeError(f"SWEGYM_CONTAINER_UNPATCHABLE_NON_ROOT:{task_id}")

            # Baseline PASS_TO_PASS, run BEFORE any patch, establishes which SPECIFIC p2p
            # tests are already broken in the unpatched image — required for
            # baseline-subtract semantics (a pre-existing p2p failure must never penalize
            # the candidate). This must compare by real per-test node id, not by
            # aggregate pass/fail: an aggregate comparison would forgive ANY post-patch
            # p2p failure whenever ANY p2p test was already broken pre-patch, including a
            # genuinely new regression the candidate patch introduced in a different,
            # previously-passing test — the exact real bug closed here.
            baseline_output = ""
            baseline_failed_ids: frozenset[str] = frozenset()
            if self._pass_to_pass:
                _baseline_passed, baseline_output, baseline_failed_ids = await self._run_tests(
                    task_id,
                    container_name,
                    self._pass_to_pass,
                    timeout=self._eval_timeout,
                    strict=False,
                )
            self._state["baseline_pass_to_pass_failures"] = sorted(baseline_failed_ids)

            test_patch_tier = await self._apply_patch(task_id, container_name, self._test_patch)
            self._state["test_patch_apply_tier"] = test_patch_tier

            if patch:
                candidate_tier = await self._apply_patch(task_id, container_name, patch)
            else:
                candidate_tier = "empty-patch-noop"
            self._state["candidate_patch_apply_tier"] = candidate_tier

            f2p_passed, f2p_output, _f2p_failed_ids = await self._run_tests(
                task_id, container_name, self._fail_to_pass, timeout=self._eval_timeout, strict=True
            )

            p2p_passed = True
            p2p_output = ""
            new_p2p_regressions: frozenset[str] = frozenset()
            if self._pass_to_pass:
                p2p_passed, p2p_output, p2p_failed_ids = await self._run_tests(
                    task_id,
                    container_name,
                    self._pass_to_pass,
                    timeout=self._eval_timeout,
                    strict=False,
                )
                if not p2p_passed:
                    # Real per-test-id baseline-subtract: a PASS_TO_PASS test failing now
                    # is only forgiven if it was ALSO in the baseline's own failed set —
                    # i.e. it was already broken before the candidate patch touched
                    # anything. Any test present in p2p_failed_ids but absent from
                    # baseline_failed_ids is a genuine new regression and must count.
                    new_p2p_regressions = p2p_failed_ids - baseline_failed_ids
                    if not new_p2p_regressions and p2p_failed_ids:
                        # Every post-patch p2p failure was already failing pre-patch --
                        # a real, per-test-verified pre-existing-failure forgiveness, not
                        # an aggregate guess.
                        p2p_passed = True
                        p2p_output += (
                            "\n[NOTE: all post-patch PASS_TO_PASS failures "
                            f"({sorted(p2p_failed_ids)}) were already failing in the "
                            "pre-patch baseline; not counted as candidate-patch regressions]"
                        )
                    elif new_p2p_regressions:
                        p2p_output += (
                            f"\n[NEW PASS_TO_PASS regressions not present in baseline: "
                            f"{sorted(new_p2p_regressions)}]"
                        )
            self._state["new_pass_to_pass_regressions"] = sorted(new_p2p_regressions)

            resolved = f2p_passed and p2p_passed

            self._state.update(
                {
                    "resolved": resolved,
                    "fail_to_pass_results": {"passed": f2p_passed, "output": f2p_output[-4000:]},
                    "pass_to_pass_results": {
                        "passed": p2p_passed,
                        "output": p2p_output[-4000:],
                        "baseline_output": baseline_output[-4000:],
                    },
                    "stdout_tail": (f2p_output + "\n" + p2p_output)[-4000:],
                }
            )
        finally:
            with anyio.move_on_after(_CONTAINER_STOP_TIMEOUT_SECONDS):
                await anyio.run_process(
                    ["docker", "rm", "-f", container_name],
                    stdout=PIPE,
                    stderr=PIPE,
                    check=False,
                )

        return {"before": before, "after": deepcopy(self._state), "image": self._image}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        return all(observed.get(key) == value for key, value in expected.items()), observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        # This is an evidence checkpoint only. Docker/the upstream image own the
        # container lifecycle; GymAct records but does not own external world state.
        return {"restorable": not self._state["attempted"], "state": deepcopy(self._state)}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if checkpoint.get("restorable") is not True:
            raise RuntimeError("SWEGYM_EXTERNAL_WORLD_RESTORE_UNSUPPORTED")
        state = checkpoint.get("state")
        if not isinstance(state, dict):
            raise TypeError("checkpoint.state must be an object")
        self._state = deepcopy(state)

    async def teardown(self) -> None:
        # Container cleanup already happened in actuate()'s finally block; nothing
        # left to release except the environment handle itself.
        self._closed = True


class SWEGymProvider:
    """Look up an admitted SWE-Gym task row without touching Docker."""

    name = "swegym"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> SWEGymEnvironment:
        task_id = config.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("SWEGYM_TASK_ID_REQUIRED")
        if scenario is not None and scenario != task_id:
            raise ValueError("SWEGYM_SCENARIO_TASK_ID_MISMATCH")

        dataset_name = config.get("dataset", SWEGYM_UPSTREAM_DATASET)
        if not isinstance(dataset_name, str) or not dataset_name:
            raise TypeError("config.dataset must be a non-empty string")
        split = config.get("split", SWEGYM_UPSTREAM_SPLIT)
        if not isinstance(split, str) or not split:
            raise TypeError("config.split must be a non-empty string")
        eval_timeout = config.get("eval_timeout", 1800)
        if not isinstance(eval_timeout, int) or isinstance(eval_timeout, bool) or eval_timeout < 1:
            raise TypeError("config.eval_timeout must be a positive integer")

        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise RuntimeError("SWEGYM_DATASET_DEPENDENCY_MISSING") from exc

        try:
            dataset = load_dataset(dataset_name, split=split)
        except Exception as exc:
            raise RuntimeError(f"SWEGYM_DATASET_UNAVAILABLE:{dataset_name}") from exc

        row: dict[str, Any] | None = None
        for candidate in dataset:
            # `datasets.Dataset.__iter__` yields dict-like rows at runtime (a real HF
            # `Dataset`/`IterableDataset` row), but its own type stubs are loose --
            # cast explicitly rather than let the ambiguity leak into `row`'s declared
            # `dict[str, Any] | None` type.
            candidate_row = dict(candidate)
            if candidate_row.get("instance_id") == task_id:
                row = candidate_row
                break
        if row is None:
            raise RuntimeError(f"SWEGYM_TASK_ID_UNKNOWN:{task_id}")

        for binary in _REQUIRED_BINARIES:
            if shutil.which(binary) is None:
                raise RuntimeError(f"SWEGYM_DEPENDENCY_MISSING:{binary}")

        repo = row.get("repo")
        base_commit = row.get("base_commit")
        test_patch = row.get("test_patch", "")
        if not isinstance(repo, str) or not repo:
            raise RuntimeError(f"SWEGYM_DATASET_ROW_MALFORMED:{task_id}")
        if not isinstance(base_commit, str) or not base_commit:
            raise RuntimeError(f"SWEGYM_DATASET_ROW_MALFORMED:{task_id}")
        if not isinstance(test_patch, str):
            raise RuntimeError(f"SWEGYM_DATASET_ROW_MALFORMED:{task_id}")

        fail_to_pass_raw = row.get("FAIL_TO_PASS")
        pass_to_pass_raw = row.get("PASS_TO_PASS")
        fail_to_pass = (
            json.loads(fail_to_pass_raw)
            if isinstance(fail_to_pass_raw, str)
            else list(fail_to_pass_raw or [])
        )
        pass_to_pass = (
            json.loads(pass_to_pass_raw)
            if isinstance(pass_to_pass_raw, str)
            else list(pass_to_pass_raw or [])
        )
        if not isinstance(fail_to_pass, list) or not all(
            isinstance(item, str) for item in fail_to_pass
        ):
            raise RuntimeError(f"SWEGYM_DATASET_ROW_MALFORMED:{task_id}")
        if not isinstance(pass_to_pass, list) or not all(
            isinstance(item, str) for item in pass_to_pass
        ):
            raise RuntimeError(f"SWEGYM_DATASET_ROW_MALFORMED:{task_id}")
        if not fail_to_pass:
            raise RuntimeError(f"SWEGYM_DATASET_ROW_MALFORMED:{task_id}")

        image = _image_for_instance(task_id)

        return SWEGymEnvironment(
            task_id=task_id,
            repo=repo,
            base_commit=base_commit,
            image=image,
            test_patch=test_patch,
            fail_to_pass=fail_to_pass,
            pass_to_pass=pass_to_pass,
            eval_timeout=eval_timeout,
        )


__all__ = [
    "SWEGYM_EVALUATE_CAPABILITY",
    "SWEGYM_UPSTREAM_DATASET",
    "SWEGYM_UPSTREAM_SPLIT",
    "SWEGymEnvironment",
    "SWEGymProvider",
]
